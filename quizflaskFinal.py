# Python Frontend for Android Endless Quiz, by Roger Wattenhofer

import random
from flask import Flask, render_template, flash, request
import threading
import time
import pyautogui
import shelve
import os
import psutil
#import pytesseract
from time import sleep

'''************************************************************ Global Variables *****************************'''
Delta = 5 # how many points winner should be ahead, can be set with ?restart=Delta
RemainingSecondsDelta = 20 # how much more can the slowest dude think?
GameWithTime = False # points = players + 1, players, players-2, etc.
QuizProgramName = 'Bluestacks.exe' # to check whether quiz is already running
QuizStartLocation = '"C:\Program Files\BlueStacks\HD-RunApp.exe"' # path and name of quiz game
ScreenScanNumber = 20 # how often to scan the screen when looking for correct result (this does not work on mac)
'''************************************************************ Webpage Calls *****************************
join game with servername:5000/?name=yourname
change settings: .../setvar?delta=5 or timelimit=20 or withtime=True or remove=somename or restart=1
************************************************************ Global Variables *****************************'''

class Player:
    def __init__(self, name, key):
        self.name = name
        self.key = key
        self.points = 0
        self.answer = 0 # as soon as answered this is a number between 1 and 4
        self.answertime = 0 # put in answer time?
        self.winner = False # not overall winner yet
        self.straggler = True  # still waiting for input

app = Flask(__name__)
#app.debug = True
app.config.from_object(__name__)
players = {}  # a set of all players, searchable by key (which players offer when they join)
lock = threading.Lock() # a lock for doing the stats so that not multiple players do it at same time
winner = False # did we find a winner already?
whoGuessedThis = ["" for i in range(5)] # texts to see what other voted
winnername = "" # to display the winner name at the end
timeLimit = -100 # if not -100, at what time will we reveal the answer?
revealing = False # to display whether we are currently revealing winner

# what could be done in the future:
# include questions and answers by stealing them from endless quiz
# better ui all over the place
# game rooms, start new games, everything more professional
# use javascript, instead of just refresh every second
# refactoring... this setup sucks.

def startGameUp():
    global region, allanswers, onMac
    found = False
    for p in psutil.process_iter():
        if QuizProgramName == p.name():
            found = True
    if not found:
        print("starting program...")
        os.system(QuizStartLocation)
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
    #if onMac:
    #    for r in region:
    #        r = tuple(list([2*i for i in r]))
    print("Region = ",region)
    print("Starting server!")
    return(region)

def testColor(result):
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
    return color

def getAutoAnswer(click):
    global region, allanswers
    #print(text)
    print("clicked (1..4) = ",click)
    r = region[click]
    x = r[0] + int(0.9 * region[0][2])
    y = r[1] + int(0.5 * region[1][3])
    sleep(2)
    result = pyautogui.screenshot(region=allanswers)
    originalgreens = testColor(result)
    beforeclick = time.time()
    pyautogui.click(x=x, y=y)
    resultseries=[]
    for x in range(ScreenScanNumber):
        #print(time.time())
        resultseries.append(pyautogui.screenshot(region=allanswers))
    greenseries=[]
    print("screen scanning time = ",time.time()-beforeclick)
    for result in resultseries:
        greenseries.append(testColor(result))
    correct = -1
    for g in greenseries:
        shifts = [a_i - b_i for a_i, b_i in zip(g, originalgreens)]
        currentmax = max(shifts)
        if currentmax > maxgreenshift:
            maxgreenshift = currentmax
            #print(maxgreenshift)
            correct = shifts.index(currentmax)
    if correct == -1:
        print("error:", shifts)
    print("correct (1..4) = ",correct+1)
    return correct+1
    #text.append(correct)
    #text.append(click - 1)
    #text.append(color)
    #db[text[0]] = text
    #sleep(randrange(5, 20))




def updatePoints(correct):
    global players, winnername, winner, whoGuessedThis, timeLimit
    allpoints = []
    whoGuessedThis = ["" for i in range(5)]
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
    timeLimit = -100
    for k in players:
        players[k].straggler = True
        players[k].answertime = 0

def evalGame():
    global players, revealing, lock
    x = lock.acquire(False)
    #print("lock free = ",x)
    if x:
        try:
            revealing = True
            clicking = []
            for k in players:
                if players[k].answer != 0:
                    clicking.append(players[k].answer)
            most = max(set(clicking), key=clicking.count)
            correct = getAutoAnswer(most)
            updatePoints(correct)
            revealing = False
        finally:
            lock.release()


def errorPage(errormsg):
    result = "<html><head><title>Quizmaster</title>"
    result +="</head><body><H1>"
    result += errormsg
    result += "</H1></body></html>"
    return result

@app.route("/setvar")
def setvar():
    global players, Delta, RemainingSecondsDelta, GameWithTime, restart, winner, timeLimit, winnername
    newdelta = request.args.get('delta', default=-1, type=int)
    if newdelta != -1:
        Delta = newdelta
        return errorPage("Delta = "+str(Delta))
    newRemainingSecondsDelta = request.args.get('timelimit', default=-1, type=int)
    if newRemainingSecondsDelta != -1:
        RemainingSecondsDelta = newRemainingSecondsDelta
        return errorPage("timelimit = "+str(RemainingSecondsDelta))
    newgameWithTime = request.args.get('withtime', default=-1, type=bool)
    if newgameWithTime != -1:
        GameWithTime = newgameWithTime
        return errorPage("withtime = " + str(GameWithTime))
    removename = request.args.get('remove', default="", type=str)
    if removename != "":
        removekey = False
        for k in players:
            if players[k].name == removename:
                removekey = k
        if not removekey:
            return errorPage("No player with name "+str(removename))
        else:
            del (players[removekey])
            return errorPage("Player "+removename+" deleted")
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
    return errorPage("use one of these ?delta=5 or timelimit=20 or withtime=True or removename=yourname or restart=1")

@app.route("/")
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
    f = open("static/main.txt")
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
            timeLimit = -100
            #sleep(min(3,max(0,timeLimit-time.time())))
            evalGame()
    replacing = {"{playername}":players[mykey].name,
                  "{playerkey}":str(players[mykey].key)}
    f = open("static/upper.txt")
    data = f.read()
    for keyword in replacing:
        data = data.replace(keyword, replacing[keyword])
    return data

@app.route("/middle")
def middleframe():
    global players, whoGuessedThis, winner, winnername, timeLimit, revealing
    mykey = request.args.get('key', default=-1, type=int)
    if winner:
        f = open("static/whoiswinner.txt")
        data = f.read()
        data = data.replace("{winnername}",winnername)
        return data
    f = open("static/middle.txt")
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
    f = open("static/whoiswinner.txt")
    data = f.read()
    data = data.replace("{winnername}", winnername)
    return data

@app.route("/lower")
def lowerframe():
    f = open("static/lower.txt")
    result = f.read()
    result += str(Delta) + ")</H2>"
    temp = []
    for key in players:
        p = players[key]
        temp.append([key, p.points])
    temp.sort(key=lambda v: -v[1])
    for x in temp:
        p = players[x[0]]
        if p.winner:
            result += "<H2><font color=\"green\">" + p.name + " " + str(p.points) + "</font></H2>"
        elif p.straggler:
            result += "<H2><font color=\"red\">" + p.name + " " + str(p.points) + "</font></H2>"
        else:
            result += "<H2>"+p.name + " " + str(p.points)+"</H2>"
    result += "</body></html>"
    return result

if __name__ == "__main__":
    startGameUp()
    app.run('0.0.0.0', use_reloader=False)
    #app.run(use_reloader=False)