# Python Frontend for Android Endless Quiz, by Roger Wattenhofer

import random
from flask import Flask, render_template, flash, request
import threading
import time
import pyautogui
import shelve
import os
from time import sleep
import psutil
#import pytesseract

#************************************************************ Global Variables *****************************
Delta = 5 # how many points winner should be ahead, can be set with ?restart=Delta
RemainingSecondsDelta = 20 # how much more can the slowest dude think?
GameWithTime = False # points = players + 1, players, players-2, etc.
programname = 'Bluestacks.exe'
#************************************************************ Webpage Calls *****************************
#join game with servername:5000/main?name=yourname
#change settings: .../setvar?delta=5 or timelimit=20 or withtime = True or removename = yourname or restart = 1
#************************************************************ Global Variables *****************************

class Player:
    def __init__(self, name, key):
        self.name = name
        self.key = key
        self.points = 0
        self.answer = 0 # as soon as answered this is a number between 1 and 4
        self.answertime = 0 # put in answer time?
        self.winner = False # not overall winner yet
        self.straggler = True  # still waiting for input

#pytesseract.pytesseract.tesseract_cmd = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
#icon = 'data/icon.PNG'
#dbname = 'data/db'
#db = shelve.open(dbname)
#pyautogui.FAILSAFE = False
#path = os.path.dirname(os.path.abspath(__file__))
#datapath = path+"/data/shelve"
#db = shelve.open(datapath)
#host = socket.gethostbyname(socket.gethostname())
# host = "82.130.102.137" # not sure which one is better, maybe even both are needed?
# main actions:
#'action', default=-1, type=str): answering, or what is correct answer: A1...C4
#'name', default=-1, type=str): register a new player
#'remove', default=-1, type=str): remove a registered player
#'key', default=-1, type=str): signal key (with each action, see above)
#'restart', default=-1, type=int): restart the game, set Delta

app = Flask(__name__)
#app.debug = True
app.config.from_object(__name__)
players = {}  # a set of all players, searchable by key (which players offer when they join)
lock = threading.Lock() # a lock for doing the stats so that not multiple players do it at same time
winner = False # did we find a winner already?
whoGuessedThis = ["" for i in range(5)] # texts to see what other voted
winnername = "" # to display the winner name at the end
timeLimit = -100 # if not -100, at what time will we reveal
revealing = False # to display whether we are currently revealing winner

# what could be done in the future:
# include questions and answers by stealing them from endless quiz
# better ui all over the place
# game rooms, start new games, everything more professional
# use javascript, instead of just refresh every second
# refactoring... this setup sucks.

'''
def startGameUp():
    global region, allanswers
    found = False
    for p in psutil.process_iter():
        if programname == p.name():
            found = True
    if not found:
        print("starting program...")
        os.system('"C:\Program Files\BlueStacks\HD-RunApp.exe"')
        sleep(40)
    else:
        print("program already running.")
    print("logo... ")
    #while True:
    #    logo = pyautogui.locateOnScreen('data/icon.PNG')
    #    if logo is not None:
    #        break
    #print("found.")
    #print("left... ")
    #if logo is not None:
    #    x = logo.left+logo.width//2
    #    y = logo.top+logo.height//2
    #    pyautogui.click(x=x, y=y, clicks=2, interval=0.25)
    i = 0
    while True:
        print(i)
        left = pyautogui.locateOnScreen('data/left'+str(i)+'.PNG')
        i = (i+1) % 4
        if left is not None:
            break
    print("found.")
    print("right... ")
    i = 0
    while True:
        print(i)
        right = pyautogui.locateOnScreen('data/right'+str(i)+'.PNG')
        i = (i+1) % 5
        if right is not None:
            break
    print("found.")
    print("Starting server!")
    l = left.left+left.width
    t = left.top
    h = left.height
    r = right.left
    w = r-l
    allanswers = (l,t,w,h)
    region = [(l, t-h//2, w, h//2)]
    for i in range(4):
        region.append((l,t+i*h//4,w,h//4))
    #print(region)
    return(region)
'''

def startGameUp():
    global region, allanswers
    found = False
    for p in psutil.process_iter():
        if programname == p.name():
            found = True
    if not found:
        print("starting program...")
        os.system('"C:\Program Files\BlueStacks\HD-RunApp.exe"')
    else:
        print("program already running.")
    print("Please start quiz now.")
    print("Please move mouse to upper left corner of the four answer boxes and hit enter")
    _ = input()
    p = pyautogui.position()
    l = p.x
    t = p.y
    print("Please move mouse to lower right corner of the four answer boxes and hit enter")
    _ = input()
    p = pyautogui.position()
    r = p.x
    h = p.y - t
    w = r - l
    allanswers = (l, t, w, h)
    region = [(l, t - h // 2, w, h // 2)]
    for i in range(4):
        region.append((l, t + i * h // 4, w, h // 4))
    print(region)
    print("Starting server!")
    return(region)

def getAutoAnswer(click):
    global region, allanswers
    #print(text)
    print("clicked (1..4) = ",click)
    r = region[click]
    x = r[0] + int(0.9 * region[0][2])
    y = r[1] + int(0.5 * region[1][3])
    pyautogui.click(x=x, y=y)
    sleep(0.3)
    # result = pyautogui.screenshot('data/result.png', region=allanswers)
    result = pyautogui.screenshot(region=allanswers)
    pix = result.load()
    s = result.size
    h = s[1] // 4
    color = []
    for i in range(4):
        sumCol = 0
        for x in range(s[0]):
            for y in range(h):
                posy = h * i + y
                sumCol += pix[x, posy][1]
        color.append(sumCol)
    #print(color)
    correct = color.index(max(color))
    print("correct (1..4) = ",correct+1)
    return correct+1
    #text.append(correct)
    #text.append(click - 1)
    #text.append(color)
    #db[text[0]] = text
    #sleep(randrange(5, 20))

def evalGame():
    global players, revealing
    revealing = True
    clicking = []
    for k in players:
        if players[k].answer != 0:
            clicking.append(players[k].answer)
    most = max(set(clicking), key=clicking.count)
    correct = getAutoAnswer(most)
    print("correct", correct)
    updatePoints(correct)
    sleep(2)
    revealing = False


def updatePoints(correct):
    global players, winnername, winner, whoGuessedThis, timeLimit
    allpoints = []
    if GameWithTime:
        sorting = []
        for k in players:
            if players[k].answer == correct:
                sorting.append([k,players[k].answertime])
                players[k].answer = 0
        sorting.sort(key=lambda i:i[1])
        #print(sorting)
        for i,p in enumerate(sorting):
            players[p[0]].points += len(players)+1-i
            #print(players[p[0]].name, len(players)+1-i)
        for k in players:
            allpoints.append(players[k].points)
    else:
        for k in players:
            if players[k].answer == correct:
                players[k].points += 1
            players[k].answer = 0
            allpoints.append(players[k].points)
    allpoints.sort()
    # print(allpoints)
    if len(players) > 1:
        if allpoints[-1] - allpoints[-2] >= Delta:
            #print("We have a winner")
            for k in players:
                p = players[k]
                if p.points == allpoints[-1]:
                    p.winner = True
                    winnername = p.name
                    winner = True
    whoGuessedThis = ["" for i in range(5)]
    timeLimit = -100
    for k in players:
        players[k].stage = "C"
        players[k].straggler = True

#def button(name, mykey):
#    return "<a href=\"/?key="+str(mykey)+"&action="+name+"\" class=\"button\"><span>"+name[1]+"</span></a>"

def errorPage(errormsg):
    result = "<html><head><title>Quizmaster</title>"
    result +="</head><body><H1>"
    result += errormsg
    result += "</H1></body></html>"
    return result

'''
def populatePage(mykey):
    # this renders the single page that we have
    global players, Delta, whoGuessedThis, winnername
    if not winner:
        me = players[mykey]
    result +="<table><tr><th>"
    if winner:
        result+="We have a Winner!!!"
    elif me.stage=="A":
        result+="Your Answer</th><th> "
    elif me.stage=="C":
        result+="The Answers</th><th>Correct Answer"
    result += "</th></tr>"
    for row in range(1,5):
        result += "<tr>"
        if winner:
            result += "<th>Winner: "+winnername+"</th>"
        elif me.stage == "A":
            text = "A"
            text += str(row)
            result += "<th><div>"+button(text,mykey)+"</div></th><th> </th>"
        elif me.stage == "C":
            result += "<th>"+whoGuessedThis[row]+"</th>"
            text = "C"
            text += str(row)
            result += "<th><div>" + button(text, mykey) + "</div></th>"
        result += "</tr>"
    result += "</table><table style=margin-left:auto;margin-right:auto>"
    result += "<tr><th>Ranking (&Delta; = "+str(Delta)+")</th></tr>"
    temp = []
    for key in players:
        p = players[key]
        temp.append([key, p.points])
    temp.sort(key=lambda v: -v[1])
    for x in temp:
        p = players[x[0]]
        result += "<tr>"
        if p.winner:
            text = "<font color=\"green\">" + p.name+" "+str(p.points)+"</font>"
        elif p.straggler:
            text = "<font color=\"red\">"+ p.name+" "+str(p.points)+"</font>"
        else:
            text = p.name+" "+str(p.points)
        result += "<th>" + text + "</th>"
        result += "</tr>"
    if winner:
        result += "<div>" + "<a href=\"/?key="+str(players[mykey].key)+"&restart="+str(Delta)+"\" class=\"button\"><span>Restart?</span></a></div>"
    result += "</body></html>"
    return result

def maybelater():
    elif a[0] == "C":
    me.straggler = False
    if me.correct == 0:
        me.correct = int(a[1])
        whoGuessedThis[me.correct] += "*"
    alldone = True
    for k in players:
        if players[k].correct == 0:
            alldone = False
            players[k].straggler = True
    if alldone:
        lock.acquire()
        allCorrects = []
        for k in players:
            allCorrects.append(players[k].correct)
        correct = max(set(allCorrects), key=allCorrects.count)
        #whoGuessedThis[correct] = "***CORRECT***\n"+whoGuessedThis[correct]
        #time.sleep(sleepTime)
        #print("test counting", allCorrects, correct)
        updatePoints(correct)
        lock.release()
            elif r != -1: # player hit restart after winner page.
                winner = False
                players[mykey].points = 0
                players[mykey].straggler = True
                players[mykey].answer = 0
                players[mykey].stage = "A"
                players[mykey].correct = 0
                players[mykey].winner = False
                winnername = ""
    return populatePage(mykey)
'''


@app.route("/setvar")
def mainframe():
    global players, Delta, RemainingSecondsDelta, GameWithTime, restart, winner, timeLimit, winnername
    newdelta = request.args.get('delta', default=-1, type=int)
    if newdelta != -1:
        Delta = newdelta
        return errorPage("Delta = ",Delta)
    newRemainingSecondsDelta = request.args.get('timelimit', default=-1, type=int)
    if newRemainingSecondsDelta != -1:
        RemainingSecondsDelta = newRemainingSecondsDelta
        return errorPage("timelimit = ", RemainingSecondsDelta)
    newgameWithTime = request.args.get('withtime', default=-1, type=bool)
    if newgameWithTime != -1:
        gameWithTime = newgameWithTime
        return errorPage("withtime = ", gameWithTime)
    removename = request.args.get('removename', default="", type=str)
    if removename != "":
        removekey = False
        for k in players:
            if players[k].name == removename:
                removekey = k
        del(players[removekey])
        if not removekey:
            return errorPage("No player with name ", removename)
        else:
            return errorPage("Player ", removename, " deleted")
    newstart = request.args.get('restart', default=-1, type=int)
    if newstart != -1:
        for p in players:
            players[p].straggler = True
            players[p].points = 0
            players[p].answer = 0
            players[p].winner = False
            players[p].answertime = 0
        winner = False
        timeLimit = -100
        winnername = ""
        return errorPage("Restarted. Please hit reload to join again!!")

@app.route("/main")
def mainframe():
    global players, Delta
    #global players, lock, Delta, winner, sleepTime, winnername
    mykey = request.args.get('key', default=-1, type=int)
    name = request.args.get('name', default=-1, type=str)
    if mykey == -1 and name == -1:
        return (errorPage("Error: no name, no key"))
    if mykey == -1:
        found = False
        for k in players:
            if players[k].name == name:
                found = True
                mykey = k
        # register a new player
        if not found:
            mykey = random.randint(1000000000,10000000000)
            me = Player(name,mykey)
            players[mykey] = me
            if GameWithTime:
                Delta = 5*len(players)
    # we now know that mykey is valid!
    f = open("../static/main.txt")
    data = f.read()
    data = data.replace("{playerkey}", str(mykey))
    return data

@app.route("/upper")
def upperframe():
    global players, whoGuessedThis, Delta, winner, winnername, timeLimit, RemainingSecondsDelta, revealing
    mykey = request.args.get('key', default=-1, type=int)
    action = request.args.get('action', default=-1, type=int)
    if action != -1:
        if not mykey in players:
            return (errorPage("Error: no valid key, your session has expired"))
        me = players[mykey]
        if timeLimit == -100:
            timeLimit = time.time() + RemainingSecondsDelta
        if me.straggler:
            me.straggler = False
            me.answertime = time.time()
            #print(me.answertime)
            me.answer = action
            if whoGuessedThis[me.answer] != "":
                whoGuessedThis[me.answer] += ", "
            whoGuessedThis[me.answer] += me.name
        alldone = True
        for k in players:
            if players[k].straggler:
                alldone = False
        if alldone:
            revealing = True
            sleep(min(3,max(0,timeLimit-time.time())))
            revealing = False
            evalGame()
    replacing = {"{playername}":players[mykey].name,
                  "{playerkey}":str(players[mykey].key)}
    f = open("../static/upper.txt")
    data = f.read()
    for keyword in replacing:
        data = data.replace(keyword, replacing[keyword])
    return data

@app.route("/middle")
def middleframe():
    global players, whoGuessedThis, winner, winnername, timeLimit, revealing
    mykey = request.args.get('key', default=-1, type=int)
    if winner:
        f = open("../static/whoiswinner.txt")
        data = f.read()
        data = data.replace("{winnername}",winnername)
        return data
    f = open("../static/middle.txt")
    result = f.read()
    if timeLimit != -100:
        timeLeft = timeLimit - time.time()
        if timeLeft < 1:
            revealing = True
        if revealing:
            result = result.replace("{remainingseconds}", "Revealing correct result...")
        elif players[mykey].straggler:
            result = result.replace("{remainingseconds}", "Answer in "+str(int(timeLeft))+"s")
        else:
            result = result.replace("{remainingseconds}", "Waiting " + str(int(timeLeft)) + "s for other players")
        if timeLeft < 0:
            evalGame()
    else:
        result = result.replace("{remainingseconds}", "Be the first to answer")
    for row in range (1,5):
        if not players[mykey].straggler:
            result = result.replace("{w}", str(row)+": "+whoGuessedThis[row], 1)
        else:
            result = result.replace("{w}", str(row)+": ",1)
    return result

@app.route("/whoiswinner")
def whoiswinnerframe():
    global players, winnername
    f = open("../static/whoiswinner.txt")
    data = f.read()
    data = data.replace("{winnername}", winnername)
    return data

@app.route("/lower")
def lowerframe():
    f = open("../static/lower.txt")
    result = f.read()
    result += str(Delta) + ")</H2>"
    temp = []
    for key in players:
        p = players[key]
        temp.append([key, p.points])
    temp.sort(key=lambda v: -v[1])
    result += "</table><table style=margin-left:auto;margin-right:auto>"
    for x in temp:
        p = players[x[0]]
        result += "<tr>"
        if p.winner:
            text = "<font color=\"green\">" + p.name + " " + str(p.points) + "</font>"
        elif p.straggler:
            text = "<font color=\"red\">" + p.name + " " + str(p.points) + "</font>"
        else:
            text = p.name + " " + str(p.points)
        result += "<th><H2>" + text + "</H2></th>"
        result += "</tr>"
    result += "</body></html>"
    return result

    return data

if __name__ == "__main__":
    startGameUp()
    app.run(host='0.0.0.0', use_reloader=False)
