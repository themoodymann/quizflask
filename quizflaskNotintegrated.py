import os
import random
from flask import Flask, render_template, flash, request
import threading
import time

class Player:
    def __init__(self, name, key):
        self.name = name
        self.key = key
        self.points = 0
        self.answer = 0
        self.correct = 0
        self.winner = False # not winner yet
        self.stage = "A" # start with answering
        self.straggler = True  # still waiting for input


app = Flask(__name__)
app.debug = True
app.config.from_object(__name__)
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

players = {}  # a set of all players, searchable by key (which players offer when they join)
lock = threading.Lock() # a lock for doing the stats so that not multiple players do it at same time
Delta = 5 # how many points winner should be ahead, can be set with ?restart=Delta
winner = False # did we find a winner already?
whoGuessedThis = ["" for i in range(5)] # texts to see what other voted
winnername = "" # to display the winner name at the end
sleepTime = 0 # currently not used, does not work correctly

# what could be done in the future
# include time to punish those which answer slowly
# don't wait for all the answers, but include a timer
# don't wait for everybody to say what correct answer is
# include questions and answers by stealing them from endless quiz
# better ui all over the place
# game rooms, start new games, everything more professional
# use javascript, instead of just refresh every second...
# refactoring... this setup sucks.
# get answers directly from screen (however, then server = game must be run at ETH, and we probably need to manually enter the answers if the server does not respond!)

def button(name, mykey):
    return "<a href=\"/?key="+str(mykey)+"&action="+name+"\" class=\"button\"><span>"+name[1]+"</span></a>"

def errorPage(errormsg):
    result = "<html><head><title>Quizmaster</title>"
    result +="</head><body><H1>"
    result += errormsg
    result += "</H1></body></html>"
    return result

def populatePage(mykey):
    # this renders the single page that we have
    global players, Delta, whoGuessedThis, winnername
    if not winner:
        me = players[mykey]
    result = "<html><head><title>Quizmaster</title>"
    if not winner:
        result += "<meta http-equiv=\"refresh\" content=\"2\">"
    result += "<link rel=\"stylesheet\" type=\"text/css\" href=\"./static/css/main.css\">"
    result += "<link rel=\"icon\" href=\"./static/favicon.ico\" type=\"image/x-icon\"/>"
    #result += "<script>refresh=window.setTimeout(function(){window.location.href=window.location.href},900000);</script>"
    result +="</head><body>"
    result += "<H2>Hey " + str(players[mykey].name) + "!</H2>"
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

@app.route("/")
# game logic: what happens with which parameters, main parameter: action!
def action():
    global players, lock, Delta, winner, whoGuessedThis, sleepTime, winnername
    mykey = 0
    a = request.args.get('action', default=-1, type=str)
    n = request.args.get('name', default=-1, type=str)
    nn = request.args.get('remove', default=-1, type=str)
    k = request.args.get('key', default=-1, type=str)
    r = request.args.get('restart', default=-1, type=int)
    if r != -1 and k == -1:
        Delta = r
        winner = False
        players = {}
        return (errorPage("Restarted: enter game again by setting name!"))
    elif nn != -1:
        found = False
        for k in players:
            if players[k].name == nn:
                thisone = k
                found = True
        if found:
            del(players[thisone])
    elif k == -1:
        if n != -1:
            found = False
            for k in players:
                if players[k].name == n:
                    found = True
                    mykey = k
            # register a new player
            if not found:
                mykey = random.randint(1000000000,10000000000)
                me = Player(n,mykey)
                players[mykey] = me
        else:
            return(errorPage("Error: no name, no key"))
    else: # there is still a key present!!
        if not int(k) in players:
            for x in players:
                print(x,players[x])
            return (errorPage("Error: no valid key, your session has expired"))
        else:
            me = players[int(k)]
            mykey = me.key
            # execute player action
            #print("Action", a, "by", me.name)
            if a != -1:
                if a[0] == me.stage:
                    if a[0] == "A":
                        me.straggler = False
                        #print("answering", a[1], int(a[1]))
                        me.answer = int(a[1])
                        if whoGuessedThis[me.answer] != "":
                            whoGuessedThis[me.answer] += ", "
                        whoGuessedThis[me.answer] += me.name
                        me.correct = 0
                        me.stage = "C"
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
                            whoGuessedThis[correct] = "***CORRECT***\n"+whoGuessedThis[correct]
                            time.sleep(sleepTime)
                            #print("test counting", allCorrects, correct)
                            allpoints = []
                            for k in players:
                                if players[k].answer == correct:
                                    players[k].points += 1
                                players[k].answer = 0
                                allpoints.append(players[k].points)
                            allpoints.sort()
                            #print(allpoints)
                            if len(players) > 1:
                                if allpoints[-1] - allpoints[-2] >= Delta:
                                    print("We have a winner")
                                    for k in players:
                                        p = players[k]
                                        if p.points == allpoints[-1]:
                                            p.winner = True
                                            winnername = p.name
                                            winner = True
                            whoGuessedThis = ["" for i in range(5)]
                            for k in players:
                                players[k].stage = "A"
                                players[k].straggler = True
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

if __name__ == "__main__":
    app.run(host='0.0.0.0')
