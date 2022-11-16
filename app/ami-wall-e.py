#!/usr/bin/env python3
disney=1
tcp_port=80
running_environment="development"
#running_environment="production"
#running_environment="tims-house"

debug=40 # turn on extra slack messages # this can be overwritten by creating /root/repos/IT/slackbot/debug or sending !debug X

# requires:
# pip3 install pyyaml
# pip3 install slackclient

################################################### VERIFY WE HAVE THE REQUIRED MODULES
#import imp
import os
import pprint,sys,platform,multiprocessing,ast,holidays,zoneinfo
from importlib import reload
from inspect import currentframe, getframeinfo 
import time, json,re, subprocess, logging, socket
from datetime import datetime, timedelta, date
import urllib.request
from random import seed
from random import random,randint
import slack_sdk
from slack_sdk.rtm import RTMClient

start_time=time.time()
import semantic_version
version=semantic_version.Version('2.0.6')
import api_auth
token=api_auth.token
botname=api_auth.botname

rtm_client = RTMClient(token=token)
sc = slack_sdk.WebClient(token=token)

if os.environ['APP_ENV']=="development":
    botname=botname + "(DEV)"
#    while 1>0:
#        print("I'm in " + os.environ['APP_ENV'] + ", so I'm ignoring the world.")
#        time.sleep(30)    
if os.environ['APP_ENV']=="production":
    botname=botname + "(PRD)"
#else: # make prod be deaf ############################################################# THIS KILLS PROD
#    while 1>0:
#        print("I'm in " + os.environ['APP_ENV'] + ", so I'm ignoring the world.")
#        time.sleep(30)
import time
start_time = time.time()

def eprint(*args, **kwargs):
    if os.environ['APP_ENV']=="production" or os.environ['APP_ENV']=="development":
        logging.warning(botname+": "+pprint.pformat(*args))
    else:
        print(pprint.pformat(*args), file=sys.stderr, **kwargs)
        
eprint("Version "+str(version))
eprint("token = "+token)
#if 'ARGOCD_PROJECT_TOKEN' in os.environ():
#    eprint(" ${ARGOCD_PROJECT_TOKEN} Token: "+ os.environ['ARGOCD_PROJECT_TOKEN'])


###################################################### FLASK INIT ########################
import flask
from flask import jsonify,render_template
app = flask.Flask(__name__,static_url_path='/static')
##########################################################################################
channelsinfo=dict()
usersinfo=dict()
filename=str(__name__)
if 'DISPLAY' in os.environ:
    if re.findall('apple',os.environ['DISPLAY']):
        logfile=filename+".log"
        running_in_openshift=False
#    elif os.environ['FLASK_RUN_FROM_CLI']:
#        logfile=filename+".log"
#        running_in_openshift=False
    else:
        logfile="/tmp/"+filename+".log"
        running_in_openshift=True
else:
    logfile="/tmp/"+filename+".log"
    running_in_openshift=True
####
if 0:
    if 'APP_ENV' in os.environ:
        if os.environ['APP_ENV']=="development":#debugging environment
            for k, v in sorted(os.environ.items()):
                eprint(str(k)+':'+ str(v))
        eprint('\n')
####
logger = logging.getLogger(botname)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("api.slack.com", 443))
ip_address=s.getsockname()[0]
s.close()

import urllib3

def getitdone(url,headers='',verify=''):
    http = urllib3.PoolManager()
    resp = http.request('GET', url)
    return resp

ipaddress=getitdone('http://timsnet.com/ip.php')

if running_in_openshift:
    #ip_address='1.2.3.4'
    logfile="/dev/stdout"

    hdlr = logging.FileHandler("/tmp/slack-"+botname+".log")
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)

    logger.setLevel(logging.ERROR)#THIS IS OPENSHIFT
    logger.warning(str(getframeinfo(currentframe()).lineno) + ": " + str(getframeinfo(currentframe()).lineno) + ": Logging for "+str(logger.getEffectiveLevel))
    logger.warning(str(getframeinfo(currentframe()).lineno) + ": " + "Running in openshift environment.")
else:
    #s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #s.connect(("api.slack.com", 443))
    #ip_address=s.getsockname()[0]
    #s.close()

    hdlr = logging.FileHandler("/tmp/slack-"+botname+".log")
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)

    logger.setLevel(logging.ERROR)#THIS IS LOCAL
    logger.critical(str(getframeinfo(currentframe()).lineno) + ": " + str(getframeinfo(currentframe()).lineno) + ": Logging for "+str(logger.getEffectiveLevel))
    logger.critical(str(getframeinfo(currentframe()).lineno) + ": " + "Running LOCAL environment.")

##################################################### LOGGING SETUP
if 1:#logging define lower
    from logging.handlers import SysLogHandler
    import logging

    logger = logging.getLogger()
#    logger.addHandler(SysLogHandler(address=('syslog.server.com'',514)))
    logger.addHandler(logging.FileHandler("/tmp/"+botname+".log"))
    logger.warning("Logging is active for "+botname)

if 0:
    try:
        imp.find_module('yaml')
    except ImportError:
        eprint("\n\nYou need to install yaml: pip3 install pyyaml\n")
        eprint("You may also need to: apt-get install python-setuptools python-dev build-essential python-pip3\n")
        eprint("You may need: apt-get install python3-pip\n")
        eprint("\n\nExiting due to requirements issue.\n")
        exit()

    try:
        imp.find_module('slackclient')
    except ImportError:
        eprint("\n\nYou need to install: pip3 install slackclient\n")
        eprint("You may need: apt-get install python3-pip\n")
        eprint("\n\nExiting due to requirements issue.\n")    
    #    exit()

if os.path.exists('app/usersinfo.txt'):
    eprint("########### found app/usersinfo.txt ")
    usersinfo_filename='app/usersinfo.txt'
    channelsinfo_filename='app/channelsinfo.json'
elif os.path.exists('usersinfo.txt'):
    eprint("########### found usersinfo.txt ")
    usersinfo_filename='usersinfo.txt'
    channelsinfo_filename='channelsinfo.json'
else:# os.path.exists('usersinfo.txt'):
    eprint("########### found none so default = /tmp/usersinfo.txt ")
    usersinfo_filename='/tmp/usersinfo.txt'
    channelsinfo_filename='/tmp/channelsinfo.json'
eprint("############################################################## USERINFO_FILENAME: "+usersinfo_filename)
################################################### BEGIN SUBROUTINES 
#from slackclient import SlackClient

#wall-e-control-channel https://hooks.slack.com/services/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
status_channel="C0496CWKY5V"
coffee_time=':coffeex: :walking: :question: '
reward='cookie'

#sc = SlackClient(token)
#sc = WebClient(token)

def grep(inputs,search):
    lines = inputs.split('\n')
    result=0
    for line in lines:
        if search in line:
            result=1
            break
    return result

def run(command,message):
    cmd_message = message.split()
    if(len(cmd_message)>1):
        hostnamef = cmd_message[1].split("|")[1].strip('>')
        hostnamef = "ansible@" + hostnamef
        ssh = subprocess.Popen(["ssh", "%s" % hostnamef, "sudo " + command],shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cmd_response = ssh.stdout.read()
        if cmd_response == []:
            error = ssh.stderr.readlines()
            logger.error(sys.stderr, "ERROR: %s" % error)
        else:
            output=str(cmd_response)
            eprint("#################################################### output = " + output)
            output=output.split("'")[1]
            output=output.replace('\\r',"\n")
            output=output.replace('\\n',"\n")
            output=output.replace('\r',"\n")
            output=output.replace('\t',"     ")
            output=output.replace('  '," ")
            output=output.replace('  '," ")
            output=output.replace('######################################','###')

        return output

def clean_output(output):
    output=str(output)
    output=output.replace('\\r',"\n")
    output=output.replace('\\n',"\n")
    output=output.replace('\r',"\n")
    output=output.replace('\t',"     ")
    output=output.replace('  '," ")
    output=output.replace('  '," ")
    output=output.replace("'","")
    return output

def date_manip(when):
    if when=='yesterday':
        NYC = zoneinfo.ZoneInfo("America/New_York")
#        datetime(2020, 1, 1, tzinfo=NYC)
        yesterday = datetime.now(tzinfo=NYC) - timedelta(days = 1)
        yesterday.strftime('%m-%d-%y')
        return yesterday

def list_users():
    global debug
#    usersinfo["TEST123"]="Test User"
    identity=sc.api_call("users.list")
    if identity["ok"]:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + "Good identity")
    else:
        logger.warning(str(getframeinfo(currentframe()).lineno) + ":list_users called sc_api and returned a bad users.list: " + str(identity["ok"]))
        return -1

    users=identity["members"]
    count=0
    for user in users:
        count=count + 1
        if user["deleted"]:
            logger.debug(str(getframeinfo(currentframe()).lineno) + ": " + "DELETED user:" + user["id"])
        if "real_name" in user:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + "user:" + user["id"] + " real_name:" + user["real_name"])
            usersinfo[user["id"]]=user["real_name"]
        elif "name" in user:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + "user:" + user["id"] + ":" + user["name"])
            usersinfo[user["id"]]=user["name"]
        else:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + "user:" + user["id"])

    return usersinfo


#    message=str(getframeinfo(currentframe()).lineno)+": "+botname+" is running on " + myhostname
#    
rtm=RTMClient(token=token)
#    sc = slack_sdk.WebClient(token=token)
#    sc.chat_postMessage(channel=status_channel,text=message) # {"channel":status_channel, "text":message}) 

def lookup_user(id):
    global token,usersinfo,usersinfo_filename,sc
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": lookup name "+pprint.pformat(id))
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": trying to find user in cache file")            
    try:
        if id in usersinfo:                    
            user=usersinfo[id]
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": CACHE-HIT! "+id+" User real_name = " + pprint.pformat(user['real_name']))
            real_name=user['real_name']
            user=usersinfo[id]
        else:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": CACHE-MISS - on lookup, no ID found in cache")
###################################################
#            sc.chat_postMessage(channel=status_channel,text=str(getframeinfo(currentframe()).lineno) + ": looking up "+id)
            user=sc.api_call(api_method="users.info",params={"user":id})
            user=user["user"]
#            sc.chat_postMessage(channel=status_channel,text=str(getframeinfo(currentframe()).lineno) + ": found "+user['real_name'])
###################################################            
#            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": users.info reports: "+pprint.pformat(str(user)))
            usersinfo[id]=user
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + id + " CACHE-MISS-ADD! User real_name = " + pprint.pformat(user['real_name']))
            if 'real_name' in user:
                real_name=user['real_name']
                logger.warning(str(getframeinfo(currentframe()).lineno) + ": " + id + " MISS! - Added id:" + id + " to usersinfo: " + user["real_name"])
            else:
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": id not found in message: "+str(evt))
        if len(usersinfo) % 10 == 1: # write file every 10 updates
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": WRITING usersinfo cache file to "+usersinfo_filename)
            with open(usersinfo_filename, 'w') as outfile:
                json.dump(usersinfo, outfile)

        return user
    except Exception as e:
        logger.error(str(getframeinfo(currentframe()).lineno) + ": exception caught on evt[text]: "+str(e))
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": exception caught on evt[text]: "+str(e))
        return

#usersinfo['URHKG0ALT']=
#eprint(lookup_user('URHKG0ALT'))
#exit(0)

def list_channels(id):
    logger.debug(str(getframeinfo(currentframe()).lineno) + ": list_channels")
    channels=sc.api_call("conversations.list",channel=id)
    if channels["ok"]:
        return channels
    else:
        logger.warning(str(getframeinfo(currentframe()).lineno) + ": failed lookup_channels ")
    return

def lookup_channel(id):
    global token,channelsinfo,sc,rtm
#    rtm=RTMClient(token=token)
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": lookup channel "+pprint.pformat(id))
    try:
        #channel=sc.api_call("conversations.info",channel=str(id))
        channel=sc.api_call(api_method="conversations.info",params={"channel":id})        
#    channel=rtm.client.conversations_info(id)
        logger.debug(str(getframeinfo(currentframe()).lineno)+" "+pprint.pformat(channel))
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": lookup channel found: "+channel['channel']['name'])
        with open(channelsinfo_filename, "w") as channels_output_file:
            channelsinfo[id]=channel['channel']
            json.dump(channelsinfo, channels_output_file, indent=4, sort_keys=True)
        return channel
    except Exception as err:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": lookup channel failed: "+str(err)) 
    return

channelsinfo[id]=lookup_channel('G01074YHFG9')


def uptime():
    global start_time
    return time.time() - start_time
    
def limit_presence_check():
    presence_count=0#presence_check()
    if os.environ['APP_ENV']=="development" and presence_count > 1:
#        global web_client
        message=botname+" is alive! Living on " + myhostname + " but I'm redundant, boooo. Shutting down"
        web_client.chat_postMessage( channel=status_channel, text=message)        
#        s.shutdown(SHUT_WR)
        time.sleep(30)

def who_am_i():
    logger.debug(str(getframeinfo(currentframe()).function)+":("+str(getframeinfo(currentframe()).lineno)+")")
    self="bot" #auth_test()
    if "ok" in self:
        return self["user"]

    return

def time_clock(channel="#studio-network-team"):#DR3T92AS0 = Tim Connolly direct
    import datetime
    import holidays
    from dateutil.easter import easter
    global web_client,reward

    day_of_week=datetime.datetime.today().strftime('%A')
    in_holidays = holidays.HolidayBase()
    holidates=holidays.US(state='CA', years=2020)
    #eprint("Easter is "+pprint.pformat({easter(int(datetime.datetime.today().strftime('%Y'))):'Easter'}))
    in_holidays.append({easter(int(datetime.datetime.today().strftime('%Y'))):'Easter'}) 
    
    this_year=int(datetime.datetime.today().strftime('%Y'))
    swd=datetime.datetime(this_year, 4, 28)
    in_holidays.append({swd: 'Star Wars Day'})

    for datestr,dname in sorted(holidates.items()):
        in_holidays.append({datestr:dname})
    today=datetime.datetime.today()
    tomorrow=datetime.datetime.today() + timedelta(days=1)
    if today in in_holidays:
        if in_holidays.get(today).startswith("Christ"):
            greeting=" Merry "
        elif in_holidays.get(today).startswith('Star Wars'):
            greeting="May the Fourth be with you! Happy "
            reward="starwarswookie"
        else:
            greeting=" Happy "
        message_out=greeting+in_holidays.get(today)+"!!"
        if in_holidays.get(today)=='Easter':
            message_out+=" :easteregg: "
        elif in_holidays.get(today).startswith('Star Wars'):
            message_out+=" :starwars: "
        web_client.chat_postMessage( channel=channel, text=message_out)
        return in_holidays.get(today)
    else:
        web_client.chat_postMessage( channel=channel, text="Good morning! Happy "+day_of_week+"!!")
        return 0

def bs():
    verbs=api_auth.verbs
    adj=api_auth.adj
    nouns=api_auth.nouns

    from random import seed,random,randint
    v=len(verbs)
    a=len(adj)
    n=len(nouns)
    x=randint(0,v)
    vx=verbs[x]
    ax=adj[randint(0,a)]
    nx=nouns[randint(0,n)]
    return vx+" "+ax+" "+nx

def lance_ism():
    phrases=api_auth.lance_ism_phrases
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
    from random import seed,random,randint
    v=len(phrases)
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
    phrase=phrases[randint(0,v)]
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
    return phrase

def deluge():
    if os.path.exists("smilies.py"):
        smilies="smilies.py"
    elif os.path.exists("app/smilies.py"):
        smilies="app/smilies.py"
    deluge = open(smilies).read()
    deluge = deluge.strip().replace('\n', ' ')
    deluge = deluge.replace(' ', '  ')
    deluge_split=deluge.split(" ")
    return deluge_split

def random_reaction():
    if os.path.exists("smilies.py"):
        smilies="smilies.py"
    elif os.path.exists("app/smilies.py"):
        smilies="app/smilies.py"
    deluge = open(smilies).read()
    deluge = deluge.strip().replace('\n', ' ')
    deluge_split=deluge.split(" ")
    from random import seed,random,randint

    count=len(deluge_split)
    x=randint(0,count)
    reaction=deluge_split[x]
    reaction=reaction.strip(":")
    return reaction

#################################################### END SUBROUTINES 


start = time.time()

if 1:
    if socket.gethostname().find('.')>=0:
        myhostname=socket.gethostname()#socket.getfqdn()
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ":"+botname+"getfqdn="+myhostname)
    else:
        myhostname=socket.getaddrinfo(socket.gethostname(), 0, flags=socket.AI_CANONNAME)[0][3]
        eprint("from ip: myhostname="+myhostname)
    if len(myhostname)>30:
        myhostname = socket.gethostname()
        eprint("myhostname override="+myhostname)

eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
if os.environ["APP_ENV"]=="development":
    myhostname="(dev):" + myhostname

#import platform
#eprint(" platform.node=" + platform.node())
#eprint("my hostname = " + myhostname + " \n\n " + "but getfqdn reports " + os.uname()[1])#socket.getfqdn(myhostname))

def modification_date(filename):
    t = os.path.getmtime(filename)
    return datetime.fromtimestamp(t).strftime("%s")

def presence_check():
    presence=sc.api_call("users.getPresence")
    presence_items=presence.items()
    
    for key, value in presence_items:
        eprint("presence_check: "+str(key)+" "+str(value))
        if key == 'connection_count':
            return value

eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
def version_check():
    if int(modification_date(__file__)) > int(start):
#        global web_client
        web_client.chat_postMessage( channel=status_channel, text=str(getframeinfo(currentframe()).lineno) + ":"+botname+" is exiting on " + myhostname + " because " + __file__ + " has changed." + "mod=" + str(int(modification_date(__file__))) + " start=" + str(int(start)))
        time.sleep(1)
#        sys.exit(0)
        os._exit(0)

def debug_check():
    import os.path
    from pathlib import Path
    my_file = Path("/var/log/slackbot/debug")
    if my_file.is_file():
        return 1
    else:
        return 0

def is_admin_user(user_id):
    if user_id in ['URHKG0ALT',#John MAcDonald
    'URHKG0ALT',#Tim Connolly
    'USH8YFG5R',#Lance Le Roux
    ]:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": Author is an admin user")
        return True
    logger.error(str(getframeinfo(currentframe()).lineno) + ": Author ("+user_id+" "+") is NOT an admin user")
    return False
eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
#debug = debug_check()
def is_automation_user(user_id):
    logger.warning("Checking user: "+user_id)
    if user_id in ['U1GSDAVM1',
    'URHKG0ALT',#Tim Connolly
    'U0B9026JU',#Ramya
    'U037QAL8T',#Lance
    'U01R67M4K1B',#Andrew Kleppinger
    'USJGXHW3T',#Ricardo Vargas
    ]:
        logger.warning(str(getframeinfo(currentframe()).lineno) + ": author is an automation user")
        return True
    logger.warning("NOT AN AUTOMATION USER: "+user_id)
    return False

def is_spn_network_user(evt):
    global usersinfo
    logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
    result=sc.api_call("conversations.members",  channel="G037QB5M5")
    logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
    eprint(evt)
    logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
    if isinstance(evt,str):
        id=evt
    elif 'user' in evt:
        id=evt['user']
    logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
    if id in usersinfo:
        logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
        user=usersinfo[id]
        logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")

    try:
        logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
        if id in result["members"]:
            logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": Author ("+user['real_name']+") is an spn_network_team user")
            return True
        else:
            eprint(result['members'])
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": Author ("+user['real_name']+") is NOT an spn_network_team user")
        logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
    except:
        logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
    logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
    return False

eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
#sc.api_call("chat.postMessage",channel=status_channel,text="I'm alive :tada:")

channel="@tim.connolly"
ingest_has_stopped=0
if debug > 0:
    interval=10
else:
    interval=60

splunk_channel="#splunk"
####################################

eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
if 0: #new method
    try:
        sc = RTMClient(token=os.environ["SLACK_APP_TOKEN"])
        print("Bot is up and running!")
#        @sc.on("message")
#        sc.start()
    except Exception as err:
        print(err)    
elif 0:
    import os

    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    # Install the Slack app and get xoxb- token in advance
    app = App(token=os.environ["SLACK_APP_TOKEN"])

    if __name__ == "__main__":
        SocketModeHandler(app, os.environ["SLACK_BOT_TOKEN"]).start()#xapp-1-AQWD9GK09-3654974307282-80ccb73f6a5668a3c306a3763ba3ab035d7887c290ada27c3d932eea24f00713
#else:
#    while not sc.rtm_connect(auto_reconnect=True):
#        sleep_time=1
#        logger.error(str(getframeinfo(currentframe()).lineno) + ": " + "Attempting reconnect! Sleep "+str(sleep_time))
#        time.sleep(sleep_time)
eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")


solo=0
value=0 #presence_check()
if os.environ["APP_ENV"]=="development":
    if value > 1:
        message=botname+" is alive! Living on " + myhostname + " but I'm redundant, boooo."
        web_client.chat_postMessage( channel=status_channel, text=message)
        time.sleep(60)
        while value>1:
            time.sleep(60)
            value=presence_check()
            logger.error(str(getframeinfo(currentframe()).lineno) + ":"+botname+" is alive! Living on " + myhostname+" but I'm redundant, boooo."+" - presence_check retured: "+str(value))
    else:
        logger.error(str(getframeinfo(currentframe()).lineno) + ":"+botname+" is alive! Living on " + myhostname + " and I'm flying solo!"+" - presence_check retured: "+str(value))
        solo=1

#Let PRD be the master if possible
if os.environ["APP_ENV"]=="development":
    failover_delay=30
else:
#PRD    
    failover_delay=10
eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
if 0:
    logger.error(str(getframeinfo(currentframe()).lineno) + ": " + "presence_check == " + str(value))
    while value > 1:#somebody else is active - could send a "!stop" to them tell where to go...
        value=presence_check()
        logger.error(str(getframeinfo(currentframe()).lineno) + ": sleeping(failover_delay) for "+str(failover_delay)+"'.")
        time.sleep(failover_delay)
        version_check()

user_list=dict()
#h=myhostname.split(".")[0] + '.' + myhostname.split(".")[1]


#if not solo:
#    web_client.chat_postMessage( channel=status_channel, text=str(getframeinfo(currentframe()).lineno)+ ": "+myhostname + " is taking over!")

bot_info=who_am_i()
bot_id="wall-e"

q = multiprocessing.Queue()#share between parent and child


eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark right before main")

#import reaction_added
@RTMClient.run_on(event="reaction_added")
def add_reaction(**payload):
    global channelsinfo
    data = payload['data']
    with open("reaction.json", 'w') as outfile:
        json.dump(data, outfile)
    web_client = payload['web_client']
    if 'channel' in data:
        logger.debug(str(getframeinfo(currentframe()).lineno) + ": found channel in data")
        evt['channel'] = data['channel']
        channel=evt['channel']
        if channel in channelsinfo:
            channel_info=channelsinfo[channel]
        else:
            channelsinfo[channel]=lookup_channel[channel]
            channel_info=channelsinfo[channel]
        o=o+channel+" "
    if "event_ts" in evt:
        timestamp=evt['event_ts']
        o=o+str(timestamp)+" "
    if "previous_message" in evt:
        logger.debug(str(getframeinfo(currentframe()).lineno) + ": found evt[previous_message]")
    if "user" in evt:
        logger.debug(str(getframeinfo(currentframe()).lineno) + ": found evt[user]")
        user={}
        if "real_name" in evt["user"]:
            user['real_name']=evt['user']
            logger.debug(str(getframeinfo(currentframe()).lineno) + ": found user[real_name]")                    
        user=evt["user"]
        if 'user_id' in user:
            id=user['user_id']
        else:
            id=evt["user"]
    logger.debug(str(getframeinfo(currentframe()).lineno) + ": reaction ("+evt['reaction']+" added")

###################################################################################################################
def set_color(org_string, level=None):
    color_levels = {
        10: "\033[36m{}\033[0m",       # DEBUG
        20: "\033[32m{}\033[0m",       # INFO
        30: "\033[33m{}\033[0m",       # WARNING
        40: "\033[31m{}\033[0m",       # ERROR
        50: "\033[7;31;31m{}\033[0m"   # FATAL/CRITICAL/EXCEPTION
    }
    if level is None:
        return color_levels[20].format(org_string)
    else:
        return color_levels[int(level)].format(org_string)
logger.info(set_color("test"))
logger.debug(set_color("test", level=10))
logger.warning(set_color("test", level=30))
logger.error(set_color("test", level=40))
logger.fatal(set_color("test", level=50))

def get_uptime():
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])

    return uptime_seconds

TIME_DURATION_UNITS = (
    ('week', 60*60*24*7),
    ('day', 60*60*24),
    ('hour', 60*60),
    ('min', 60),
    ('sec', 1)
)

def human_time_duration(seconds):
    if seconds == 0:
        return 'inf'
    parts = []
    for unit, div in TIME_DURATION_UNITS:
        amount, seconds = divmod(int(seconds), div)
        if amount > 0:
            parts.append('{} {}{}'.format(amount, unit, "" if amount == 1 else "s"))
    return ', '.join(parts)
###################################################################################################################


@RTMClient.run_on(event="user_status_changed_disabled")
def status_change(**payload):
    try:
        eprint(str(getframeinfo(currentframe()).function) + " called:")

        eprint(pprint.pformat(payload)) 
        global channelsinfo,usersinfo
        data = payload['data']#{"user": "URHKG0ALT", "reaction": "+1::skin-tone-3", "item": {"type": "message", "channel": "G01074YHFG9",
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": status change for user: "+event['user'])
        web_client = payload['web_client']
        if 'channel' in data:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found channel in data")
            evt['channel'] = data['channel']
            channel=evt['channel']
            if channel in channelsinfo:
                channel_info=channelsinfo[channel]
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found channel: "+channel_info['name'])            
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": channel_info: "+json.dumps(channel_info))
            else:
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": channel not in channelsinfo")
                channelsinfo[channel]=lookup_channel[channel]
                channel_info=channelsinfo[channel]
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": channel_info: "+json.dumps(channel_info))
            o=o+channel+" "
        if "event_ts" in evt:
            timestamp=evt['event_ts']
            o=o+str(timestamp)+" "
        if "previous_message" in evt:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found evt[previous_message]")
        if "user" in evt:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found evt[user]")
            user={}
            if "real_name" in evt["user"]:
                user['real_name']=evt['user']
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found user[real_name]")                    
            user=evt["user"]
            if 'user_id' in user:
                id=user['user_id']
            else:
                id=evt["user"]
        eprint(str(getframeinfo(currentframe()).function) + ": finished")
        return
    except Exception as e:
        logger.error(str(getframeinfo(currentframe()).function)+" "+str(getframeinfo(currentframe()).lineno) + " exception: "+str(e)) 
        

eprint("###################################################################################################### Main ################################################################")
@RTMClient.run_on(event="message")
def message(**payload):
    global usersinfo_filename,web_client,reward,version,channelsinfo,debug,usersinfo
    data = payload['data']
    web_client = payload['web_client']
    if "data" in payload:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found data in payload")
        evt=payload['data']
    if "text" in evt:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found text in evt")
        message=evt['text']
    try:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": set user_id ("+user_id+")")
        user_id=evt['user']
    except:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": normal - exception on evt['user'] - no user data")
#        eprint(evt) 
    o=''
    sc=payload['web_client']
    if 'channel' in data:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found channel in data")
        evt['channel'] = data['channel']
        channel=evt['channel']
        try:
            if channel in channelsinfo:
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": grabbing channel info for "+channel)
                logger.debug(channelsinfo)
                channel_info=channelsinfo[channel]
                if "name" in channel_info:
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found channel: "+channel_info['name'])            
                else:
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": channel_info: "+json.dumps(channel_info))
            else:
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": channel not in channelsinfo")
                channelsinfo[channel]=lookup_channel(channel)
                channel_info=channelsinfo[channel]
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": dumping channel_info - !recent_channel_dump - to retrieve ")#+json.dumps(channel_info))
        except:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": missed channelsinfo[channel]")
        o=o+channel+" "
    if "event_ts" in evt:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found timestamp (reply/thread)")
        timestamp=evt['event_ts']
        o=o+str(timestamp)+" "
    if "previous_message" in evt:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found evt[previous_message]")
#    user={}
    if "user" in evt:
        user=lookup_user(evt["user"])
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found evt[user]: "+user['real_name'])#pprint.pformat(user))

###############################################################################################################################################
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": done setting message types: "+o)
    logger.debug(str(getframeinfo(currentframe()).lineno) + ": hit bottom of conditionals on message: " +pprint.pformat(evt))




    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
    if "subtype" not in evt or evt["subtype"] != "bot_message":
#        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
        if "text" in evt:
#            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
            try:
                message=evt['text']
#                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
            except Exception as e:
                logger.error(str(getframeinfo(currentframe()).lineno) + ": exception caught on evt[text]: "+str(e))
#                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": exception caught on evt[text]: "+str(e))
#        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
        try:
            if user:
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": not bot - ("+user["real_name"]+") message=" + pprint.pformat(message))
            else:
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": not bot - (no user info) evt=" + pprint.pformat(message))
        except Exception as e:
            logger.error(str(getframeinfo(currentframe()).lineno) + ": exception caught on user: "+str(e))
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": exception caught on user: "+str(e)+"\n\nUser:\n"+pprint.pformat(user))                
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": ! message check")
        if message.startswith("!"):
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": beginning ! message lookups")
            try:
                if message.startswith("!hi"):
                    eprint(user)
                    logger.warning(str(getframeinfo(currentframe()).lineno) + ": " + "Hi from "+user['real_name'])
                    web_client.chat_postMessage(channel=channel, text=myhostname + ": Hello there! Use !info for more...info!")                
                elif message.startswith("!version"):
                    date_time="2099-07-31 15:03:32" # blah
                    logger.warning(str(getframeinfo(currentframe()).lineno) + ": " + " version request: "+str(version))
                    web_client.chat_postMessage(channel=channel, text=myhostname + ": Version: "+str(version))
                elif message.startswith("!stop"):
                    message=myhostname + ": Stopping"
                    web_client.chat_postMessage(channel=channel, text=message)
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": " + "Stopping RTM due to !stop command.")
                    stop_rtm()
#                    sys.exit(0)                     
                elif message.startswith("!start"):
                    message=myhostname + ": Starting"
                    web_client.chat_postMessage(channel=channel, text=message)
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": " + "Starting RTM due to !start command.")
                    start_rtm()
                elif (message.startswith("!adze ")):# and (is_spn_network_user(evt))):
                    logger.error(str(getframeinfo(currentframe()).lineno) + ": mark") 
                    cmd_message = message.split()
                    #sc.api_call  ("reactions.add", -> web_client.reactions_add(
                    web_client.reactions_add(channel=channel, name='axe', timestamp=timestamp)



                    if 1:
                        view='SPN'
                        group='spn'
                        search=str()
                        output=str()
                        logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")   
                        if len(cmd_message)>0:
                            cmd=cmd_message
                            logger.error(str(getframeinfo(currentframe()).lineno) + ": mark") 
                            if len(cmd) > 3:
                                logger.error(str(getframeinfo(currentframe()).lineno) + ": mark") 
                                view = cmd[1]
                                group = cmd[2]
                                search = cmd[3]
                                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+" view="+view+" group="+group+" search="+search)
                            elif len(cmd) > 2:
                                logger.error(str(getframeinfo(currentframe()).lineno) + ": mark") 
                                group = cmd[1]
                                search = cmd[2]
                                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+" view="+view+" group="+group+" search="+search)
            #                                    output+="Normally call with !command <view> <group> <search string>\n"
                            elif len(cmd) > 1:
                                logger.error(str(getframeinfo(currentframe()).lineno) + ": mark") 
                                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno))
                                search = cmd[1]
                                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+" view="+view+" group="+group+" search="+search)
            #                                    output+="Normally call with !command <view> <group> <search string>\n"
                        logger.error(str(getframeinfo(currentframe()).lineno) + ": mark") 
                        if search:
                            logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")

                            adze_hostname='ansible-inventory.studio.disney.com' #prod
                            adze_hostname='ansible-inventory.ss-nonprod.studio.disney.com' # non-prod
                            url='https://'+adze_hostname+'/api/adze/v2/'+view+'/'+group
            #                                url="http://timsnet.com/ip.php"
                            logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
                            try:
                                logger.error(str(getframeinfo(currentframe()).lineno) + ": mark") 
            # curl -H '{"x-token":"spn-ld9643x77O1fyf","HTTP_X_TOKEN":"spn-ld9643x77O1fyf"}' https://ansible-inventory.studio.disney.com/api/adze/v2/SPN/spn --header 'x-token: spn-ld9643x77O1fyf'
                                token_hash='spn-ld9643x77O1fyf'
                                headers={'x-token':token_hash.encode(),'cache-control':'no-cache'}
                                r=getitdone(url,headers=headers, verify=False) # resp.data.decode('utf-8')
                                if r.status>200:
                                    output=str(r.status)+" ADZE engine request failed. URL="+url
                                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+" mark")
                                else:
                                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+" mark")
                                    try:
                                        rj=json.loads(r.data.decode('utf-8'))
                                    except Exception as e:
                                        logger.error(str(getframeinfo(currentframe()).lineno) + ": mark") 

                                        output=str(getframeinfo(currentframe()).lineno)+" Excpetion caught: "+str(e)
                                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+" mark")
                                    meta=rj['_meta']
                                    hostvars=meta['hostvars']
                                    output+="Results:\n"
                                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+" mark")
                                    for hostname in hostvars:
                                        if search in hostname:
                                            if 'ipv4addr0' in hostvars[hostname]:
            #                                                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+" hostvars="+pprint.pformat(hostvars))
                                                ip=hostvars[hostname]['ipv4addr0']
                                                output+="ssh://"+hostname+" "+ip+"\n"
                                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+" mark")
                            except Exception as e:
                                logger.error(str(getframeinfo(currentframe()).lineno) + ": mark") 
                                output=str(getframeinfo(currentframe()).lineno)+" Excpetion caught: "+str(e)
                        else:
                            logger.error(str(getframeinfo(currentframe()).lineno) + ": mark") 
                            output="No search found: args="+str(len(cmd))+"\n"
                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+" thread_ts="+evt["ts"])
                        # web_client.chat_postMessage(-> web_client.chat_postMessage(
                        web_client.chat_postMessage(channel=channel, text=output, thread_ts=evt["ts"])
                    logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
                elif message.startswith("!good_morning"):
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": GOOD_MORNING message")
                    web_client.reactions_add(channel=channel, name='good-morning', timestamp=timestamp)
                    web_client.reactions_add(channel=channel, name='coffee', timestamp=timestamp)
                    web_client.reactions_add(channel=channel, name='doughnut', timestamp=timestamp)                    
                    web_client.chat_postMessage( channel=channel, text="Good morning!!")
                elif message.startswith("!wonkey"):#https://www.youtube.com/watch?v=SDeQT9zCvi4
                    web_client.reactions_add(channel=channel, name='wonkey_donkey', timestamp=timestamp)
                    web_client.chat_postMessage(channel=channel,thread_ts=evt["ts"],attachments='[{"title":"WONKEY DONKEY","image_url":"https://www.youtube.com/watch?v=SDeQT9zCvi4"}]')
#                web_client.chat_postMessage( channel=channel, text="", thread_ts=evt["ts"],
#                attachments='[{"title":"UPGRAYEDD","image_url":"https://pbs.twimg.com/media/E4uxqv-XwAU_Ar3.jpg"}]')                    



        #duo_user_get(username                            
        ############################## DUO Related 
                elif message.startswith("!duo"):#is_spn_network_user(evt["user"]) and
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": DUO message")
                    logger.warning(str(getframeinfo(currentframe()).lineno) + ": importing spn_duo_functions")
                    import spn_duo_functions
                    logger.warning(str(getframeinfo(currentframe()).lineno) + ": finished import")
                    cmd = message.split()
                    cmd_structure={'user':['lookup','activate','lockedout']}#,'ipam':['lookup','reserve'],'vlan':['lookup']}
                    help_message="First level commands:\n"
                    help_message=help_message+" user:\n"
                    help_message=help_message+"   lookup <username> - check an individual user status\n"
                    help_message=help_message+"   activate <username> - force a user status to be active.\n"
                    help_message=help_message+"   lockedout - show list of users on the lockout list\n"                    
                    output='initial output'
                    if len(cmd)>3:
                        web_client.reactions_add(channel=channel, name='duo', timestamp=timestamp)
                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": DUO len(cmd)>3")
                        obj=cmd[1]
                        action=cmd[2]
                        username=cmd[3]
                        if 1:#try:
                            if action=='lookup':
                                results='DUO results for username: '+username+':```'
                                output=spn_duo_functions.duo_user_get(username)
                                web_client.chat_postMessage( channel=channel, text=user['realname']+"("+user['username']+"): "+user['status']+"\n", thread_ts=evt["ts"]) 
                            elif action.startswith('acti'):#!duo user activate <username>
                                output='DUO activate username: '+username+':'
                                user=spn_duo_functions.duo_unlock_user(username)
                                web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"]) 
                            else:
                                output="Unknown action name: "+cmd[0]+" "+action+"\n"+help_message
                    elif len(cmd)>2:
                        logger.warning(str(getframeinfo(currentframe()).lineno) + ": cmd > 2 ")
                        web_client.reactions_add(channel=channel, name='walledlp', timestamp=timestamp)
                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": DUO len(cmd)>2")
                        obj=cmd[1]
                        action=cmd[2]                                
                        if action=='lockedout':
                            logger.warning(str(getframeinfo(currentframe()).lineno) + ": calling spn_duo_functions.duo_get_users_locked_out")
                            users=spn_duo_functions.duo_get_users_locked_out()
                            output='    Users locked out in DUO:\n'
                            for user in users:
                                output+=user['realname']+"("+user['username']+"): "+user['status']+"\n"
                        else:
                            output="Unknown action: "+action
                        logger.warning(str(getframeinfo(currentframe()).lineno) + ": mark") 
                    elif len(cmd)>1:
                        logger.warning(str(getframeinfo(currentframe()).lineno) + ": mark") 
                        web_client.reactions_add(channel=channel, name='walledlp', timestamp=timestamp)
                        module=cmd[1]
                        if module.lower()=='help':
                            output="Help message:\n"
                            for module in cmd_structure:
                                actions=cmd_structure[module]
                                for action in actions:
                                    output+=module+" "+action+"\n"
                            output=output+"\n"+help_message

                    else:
                        logger.warning(str(getframeinfo(currentframe()).lineno) + ": mark") 
                        output="Bad input.\nTry: !duo <action> <object> - e.g.\n!duo lookup connt047\n!duo user lockedout\n!duo help - for more options"
                    logger.warning(str(getframeinfo(currentframe()).lineno) + ": mark")
                    web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"]) 
                    logger.warning(str(getframeinfo(currentframe()).lineno) + ": duo finished") 
                elif message.startswith("!lanc"):
                    logger.error(str(getframeinfo(currentframe()).lineno) + ": Lance-ism")
                    message_back=lance_ism()
                    eprint("!lancism = "+message_back)
                    web_client.reactions_add(channel=channel, name='lance-4450', timestamp=timestamp)
                    web_client.chat_postMessage(channel=channel, text=message_back, timestamp=timestamp,thread_ts=evt["ts"])#"DR3T92AS0"
                elif message.startswith("!csr "):
                    logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
                    web_client.reactions_add(channel=channel, name='walledlp', timestamp=timestamp)
                    if len(message.split(" "))>1:
                        for _ in range(int(message.split(" ")[1])):         
                            try:
                                message_back+=csr()+"Job submitted\nResponse will go here: #spn-network-automation"
                            except NameError:
                                message_back="Error submitting job\n"            
                    else:
                        web_client.reactions_add(channel=channel, name='facepalm', timestamp=timestamp)
                        message_back="You need to provide the FQDN"
                    web_client.chat_postMessage(channel=channel, text=message_back, timestamp=timestamp,thread_ts=evt["ts"])                                                           
                elif message.startswith("!bs"):
                    logger.error(str(getframeinfo(currentframe()).lineno) + ": mark")
                    if len(message.split(" "))>1:
                        for _ in range(int(message.split(" ")[1])):
                            try:
                                message_back+=bs()+"\n"
                            except NameError:
                                message_back=bs()+"\n"
                    else:
                        message_back=bs()
                    web_client.chat_postMessage(channel=channel, text=message_back, timestamp=timestamp,thread_ts=evt["ts"])#"DR3T92AS0"
                elif "/links" in message or "!links" in message:
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": LINKS message matched: ")
                    web_client.reactions_add(channel=channel, name='lego-vader', timestamp=timestamp)
                    output=" !secret - password encrypter\n !compliance - compliance training\n"
                    output= output + " !zoom - link to Disney zoom login\n"
                    output= output + " !vacation - link to Vacation request instructions\n"
                    output= output + " !oncall - link to On-Call schedule\n"
                    output= output + " !logic - link to LogicMonitor schedule\n"
                    web_client.chat_postMessage( channel=channel, text=output,timestamp=timestamp,thread_ts=evt["ts"])
                elif message=="!usersinfo":
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": messages matched: "+message)
                    all_user_info={}
                    output=''
                    for user_id in usersinfo:
                        user=usersinfo[user_id]
                        output+=pprint.pformat(user_id+" "+user['real_name'])
                    output+=''
                        #all_user_info[user_id]=usersinfo[user_id]['profile']['real_name']
                    web_client.chat_postMessage( channel=channel, text="Currently ("+str(len(usersinfo))+") cached users: "+jsonify(pprint.pformat(output)))
                    #logger.warning(pprint.pformat(output))
                    #logger.warning(pprint.pformat(usersinfo[user_id]))
## NEW FUNCTIONS GO HERE ##
## ADD THE FUNCTION TO THE LIST IN THE HELP COMMAND ABOVE ##

                elif "/logic" in message or "!logic" in message:
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": LOGICMONITOR message matched: ")
                    web_client.reactions_add(channel=channel, name='obiwan', timestamp=timestamp)
                    output="This IS the link you are looking for: https://disneystudios.logicmonitor.com/"
                    web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"])                            
                elif "/oncall" in message or "!oncall" in message or "/on-call" in message or "!on-call" in message:
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": ONCALL message matched: ")
                    web_client.reactions_add(channel=channel, name='obiwan', timestamp=timestamp)
                    output="This IS the link you are looking for: https://confluence.platform.wds.io/calendar/spacecalendar.action?spaceKey=SPN"
                    web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"])                            
                elif "/vaca" in message or "!vaca" in message:
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": VACA message matched: ")
                    web_client.reactions_add(channel=channel, name='obiwan', timestamp=timestamp)
                    output="This IS the link you are looking for: https://app.smartsheet.com/b/form/daec8acf7e4e48a7870a83cb100339b0"##https://teams.microsoft.com/l/channel/19%3Aab723da04a5948c2bec1226bfeeaaa5d%40thread.skype/tab%3A%3A0d33a398-b6fb-4568-a4e6-22484f6352db?groupId=6bc908fd-1c59-4134-840b-b58eac76666f&tenantId=56b731a8-a2ac-4c32-bf6b-616810e913c6"
#                            https://twdc.sharepoint.com/:w:/r/sites/StudiosProductionNetwork/_layouts/15/Doc.aspx?sourcedoc=%7BD3175684-5B21-446A-87C8-2F75897FA409%7D&file=Vacation%20and%20OOO%20requests.docx&action=default&mobileredirect=true"
                    web_client.chat_postMessage(as_user="true", channel=channel, text=output, thread_ts=evt["ts"])
                elif "/logic" in message or "!logic" in message:
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": LOGICMONITOR message matched: ")
                    web_client.reactions_add(channel=channel, name='obiwan', timestamp=timestamp)
                    output="This IS the link you are looking for: https://disneystudios.logicmonitor.com/"
                    web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"])                            
                elif "/oncall" in message or "!oncall" in message or "/on-call" in message or "!on-call" in message:
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": ONCALL message matched: ")
                    web_client.reactions_add(channel=channel, name='obiwan', timestamp=timestamp)
                    output="This IS the link you are looking for: https://confluence.platform.wds.io/calendar/spacecalendar.action?spaceKey=SPN"
                    web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"])                            
                elif "/vaca" in message or "!vaca" in message:
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": VACA message matched: ")
                    web_client.reactions_add(channel=channel, name='obiwan', timestamp=timestamp)
                    output="This IS the link you are looking for: https://app.smartsheet.com/b/form/daec8acf7e4e48a7870a83cb100339b0"##https://teams.microsoft.com/l/channel/19%3Aab723da04a5948c2bec1226bfeeaaa5d%40thread.skype/tab%3A%3A0d33a398-b6fb-4568-a4e6-22484f6352db?groupId=6bc908fd-1c59-4134-840b-b58eac76666f&tenantId=56b731a8-a2ac-4c32-bf6b-616810e913c6"
#                            https://twdc.sharepoint.com/:w:/r/sites/StudiosProductionNetwork/_layouts/15/Doc.aspx?sourcedoc=%7BD3175684-5B21-446A-87C8-2F75897FA409%7D&file=Vacation%20and%20OOO%20requests.docx&action=default&mobileredirect=true"
                    web_client.chat_postMessage(as_user="true", channel=channel, text=output, thread_ts=evt["ts"])
                elif "/secret" in message or "!secret" in message:
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": SECRET message matched: ")
                    web_client.reactions_add(channel=channel, name='obiwan', timestamp=timestamp)
                    output="This IS the link you are looking for: https://pwpusher.platform.wds.io/"
                    web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"])
                elif "/compliance" in message or "!compliance" in message:
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": COMPLIANCE message matched: ")
                    web_client.reactions_add(channel=channel, name='obiwan', timestamp=timestamp)
                    output="This IS the link you are looking for: https://disney.service-now.com/sp_gecm/"
                    web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"])    
                elif "/map" in message or "!map" in message:
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": MAP message matched: ")
                    web_client.reactions_add(channel=channel, name='round_pushpin', timestamp=timestamp)
                    output="This IS the link you are looking for: https://confluence.disney.com/display/DCREO/CAMPUS+MAPS"
                    web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"])                               
                elif message.startswith("!test"):
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": TEST message matched: ")
                    output=str(int(time.strftime("%H")))
                    web_client.chat_postMessage( channel=channel, text=output)
                elif "/compliance" in message or "!compliance" in message:
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": COMPLIANCE message matched: ")
                    web_client.reactions_add(channel=channel, name='obiwan', timestamp=timestamp)
                    output="This IS the link you are looking for: https://disney.service-now.com/sp_gecm/"
                    web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"])    
                elif "/map" in message or "!map" in message:
                    logger.info(str(getframeinfo(currentframe()).lineno) + ": MAP message matched: ")
                    web_client.reactions_add(channel=channel, name='round_pushpin', timestamp=timestamp)
                    output="This IS the link you are looking for: https://confluence.disney.com/display/DCREO/CAMPUS+MAPS"
                    web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"])                               

                elif message.startswith("!help"):
                    text=str(getframeinfo(currentframe()).lineno) + ":Available commands:\n"
                    commands = ['hi - are you there?',
                                    'info - what platform is this',
                                    'heya - are you alive?',
                                    'help - you are looking at it!',
                                    'usersinfo - list cached slack users',
                                    'corona - get stats on CV19 CoronaVirus',
                                    'say #<channel> <what to say> - make announcement for me',
                                    'stop - stop '+botname+', ICE','reload - refresh '+botname,
                                    'secret - send the link for the password pusher',
                                    'debug <x> - set debugging value on the '+botname]
                    command_list = ''
                    all_commands = ['hi - are you there?',
                                    'info - what platform is this',
                                    'heya - are you alive?',
                                    'help - you are looking at it!',
                                    'usersinfo - list cached slack users',
                                    'corona - get stats on CV19 CoronaVirus',
                                    'ilo - retrieve ILO IP',
                                    'say #<channel> <what to say> - make announcement for me',
                                    'mtu <fqdn> - check mtu',
                                    'uname <fqdn> - check uname -a',
                                    'lldp <fqdn> - show physical connections on eth0',
                                    'lsi <fqdn> - basic lsi drives display',
                                    'megaraid <fqdn> - list virtual drives and state',
                                    'make-active - set <FQDN> active in the hosts table',
                                    'make-inactive - set <FQDN> inactive in the hosts table',
                                    'vpn - list active vpn sessions',
                                    'uptime <fqdn> - show uptime of host',
                                    'decomm-nagios <fqdn> - disable monitoring of host',
                                    'version <fqdn> - OS version check',
                                    'stop - stop '+botname+', ICE','reload - refresh '+botname,
                                    'splunk-license-status - check the license status on the main slpunk server',
                                    'splunk-XXXX <fqdn> - start/stop/status splunk agent on host',
                                    'slave-status <fqdn> - check mysql replication slave status',
                                    'wth <fqdn> - What Type of Hardware?','df <fqdn> - disk usage',
                                    'top <fqdn> - run top on remote host','w00t - need I say more?',
                                    'debug <x> - set debugging value on the '+botname]
                    for command in commands:
                        command_list +="\t!" + command + "\n"
                    web_client.chat_postMessage( channel=channel, text=text + command_list,timestamp=timestamp,thread_ts=evt["ts"])
                elif message.startswith("!info"):
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + "Hi from "+real_name)
                    msg="IP_Address: "+ip_address+"\n"
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
                    try:
                        for line in os.uname():
                            msg+=line+"\n"
                        msg+="Uptime "+human_time_duration(get_uptime())+"\n"
                    except:
                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
                    eprint(msg)
                    web_client.chat_postMessage( channel=channel, text=str(myhostname) + " is running on:\n"+msg,timestamp=timestamp,thread_ts=evt["ts"])
                elif message.startswith("!acro"):
                    eprint(str(api_auth.acronyms))
                    
                    try:
                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": acro list")
                        output=""
                        matches=0
                        cmd_message = message.split()
                        if(len(cmd_message)>1):
                            search=cmd_message[1].upper()
                            for acronym in api_auth.acronyms:
                                if search in acronym:
                                    output=output+"\n"+acronym
                                    matches+=1
                            if matches < 1:
                                output=" None found. "
                            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": acro command: "+search)
#                            output=grep(api_auth.acronyms,search)
#                            eprint(str(api_auth.acronyms))
                            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": acro result: "+output)
                    except Exception as e:
                        eprint("Exception: "+str(e))
#                    for command in commands:
#                        command_list +="\t!" + command + "\n"
                    web_client.chat_postMessage( channel=channel, text=output,timestamp=timestamp,thread_ts=evt["ts"])

#ARCI - which is an acronym for Accountable, Responsible, Consulted and Informed - is a responsibility assignment framework designed to bring structure and clarity to the roles people play on a project and its individual goals.




                elif message.startswith("!debug"):
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": debug modify command")
                    old_debug = debug#logger.getLogger()
                    cmd_message = message.split()
                    if(len(cmd_message)>1):
                        debug = cmd_message[1]
                        debug = int(debug.strip('>'))
                        #levels = {0:logging.DEBUG, 1:logging.INFO, 2:logging.WARNING, 3:logging.ERROR, 4:logging.CRITICAL}
                        if debug>40:
                            logger.setLevel(logging.DEBUG)
                        elif debug>30:
                            logger.setLevel(logging.INFO)
                        elif debug>20:
                            logger.setLevel(logging.WARNING)
                        elif debug>10:
                            logger.setLevel(logging.ERROR)
                        elif debug>0:
                            logger.setLevel(logging.CRITICAL)
                        else:# debug==0:
                            logger.setLevel(logging.NOTSET)
                        message="debug mode change: " + str(old_debug) + " to " + str(debug)
                    else:
                        message="debug currently at "+str(old_debug)

                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + message)
                    web_client.chat_postMessage( channel=channel, text=myhostname + ":" + message)
        #                                

                elif message.startswith("!deluge"):
                    web_client.reactions_add(channel=channel, name='fireball', timestamp=timestamp)
                    deluge_list=deluge()
                    for deluge in deluge_list:
                        reaction=deluge.strip(":")
#                    web_client.chat_postMessage(channel=channel, text='deluge=' + deluge)
                        web_client.reactions_add(channel=channel, name=reaction, timestamp=timestamp)            

                elif message.startswith("!"):
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + "###################### Unknown ! command found: " +pprint.pformat(evt))
            except Exception as e:
                logger.error(str(getframeinfo(currentframe()).lineno) + ": exception caught on user: "+str(e))
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": exception caught on user: "+str(e)+"\n\nUser:\n"+pprint.pformat(user))   
############################################################### END OF COMMAND MESSAGE PARSING !xxxx #######################################################

        else:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": not a ! message")
            if re.match(r'.*?#*\s?(1050)',message,re.IGNORECASE):
                web_client.reactions_add(channel=channel, name='bb8-thumbsup-1050', timestamp=timestamp)
            elif re.match(r'(.*?#*){0,3}\s?(wookie)',message,re.IGNORECASE):
                web_client.reactions_add(channel=channel, name='wookie_dancing', timestamp=timestamp)
            elif re.match(r'(.*?#*){0,3}\s?(lucky)',message,re.IGNORECASE):
                web_client.reactions_add(channel=channel, name='luckyparrot', timestamp=timestamp)
            elif re.match(r'(.*?#*){0,3}\s?(\sblood\s)',message,re.IGNORECASE):
                web_client.reactions_add(channel=channel, name='vampie', timestamp=timestamp)    
            elif re.match(r'.*?#*\s?(heading|leaving)',message,re.IGNORECASE) or message.startswith("##"):
                portals=['parrot_portal']#,'portal-parrot','portal-parrot-blue','portal-parrot-orange','portalblueparrot','portalparrotblue','portalparrotorange']
                for portal in portals:
                    web_client.reactions_add(channel=channel, name=portal, timestamp=timestamp)
            elif re.match(r'.*?#*\s?(can\sof\sworms)',message,re.IGNORECASE):
                web_client.reactions_add(channel=channel, name='can_of_worms', timestamp=timestamp)
            elif re.match(r'.*?#*\s?(risk|risky)',message,re.IGNORECASE):
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": RISK message")
                web_client.reactions_add(channel=channel, name='shady_blob', timestamp=timestamp)   
            elif re.match(r'.*?#*\s?(panic|panick)',message,re.IGNORECASE):
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": PANIC message")
                web_client.reactions_add(channel=channel, name='dont_panic', timestamp=timestamp)                                                     
            elif re.match(r'.*?#*\s?(north\sring|northring)',message,re.IGNORECASE):
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": NORTH RING message")
                web_client.reactions_add(channel=channel, name='north', timestamp=timestamp)
                web_client.reactions_add(channel=channel, name='ring', timestamp=timestamp)
            elif re.match(r'.*?#*\s?(elvis)',message,re.IGNORECASE):
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": ELVIS message")
                web_client.reactions_add(channel=channel, name='elvis', timestamp=timestamp)
            elif re.match(r'.*?#*\s?(lunch)',message,re.IGNORECASE):#(.*?#*){0,3}\s?....
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": LUNCH message")
                web_client.reactions_add(channel=channel, name='lunchtime', timestamp=timestamp)
            elif re.match(r'.*?#*\s?(sick|puke)',message,re.IGNORECASE):
                web_client.reactions_add(channel=channel, name='puke', timestamp=timestamp)                            
            elif re.match(r'.*?#*\s?(see\sdead\speople)',message,re.IGNORECASE):
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": GHOST message")
                web_client.reactions_add(channel=channel, name='ghost', timestamp=timestamp)                            
            elif re.match(r'.*?#*\s?(this\sis\sthe\sway)',message,re.IGNORECASE):
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": THIS_IS_THE_WAY message")
                web_client.reactions_add(channel=channel, name='mandalorian', timestamp=timestamp)
                web_client.reactions_add(channel=channel, name='mandalore', timestamp=timestamp)
            elif re.match(r'.*?#*\s?(completed|complete|done)',message,re.IGNORECASE):
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": COMPLETE/DONE message")
                message_back='@'+user['profile']['display_name_normalized']+' '+reward
                web_client.reactions_add(channel=channel, name=reward, timestamp=timestamp)
            elif re.match(r'.*?#*\s?(good\smorning)',message,re.IGNORECASE):
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": GOOD MORNING message")
                web_client.reactions_add(channel=channel, name='good-morning', timestamp=timestamp)
                web_client.reactions_add(channel=channel, name='coffee', timestamp=timestamp)
                web_client.reactions_add(channel=channel, name='doughnut', timestamp=timestamp)
            elif re.match(r'.*?#*\s?(\sISE\s)',message,re.IGNORECASE):
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": ISE message")
                web_client.reactions_add(channel=channel, name="icecold", timestamp=timestamp)
            elif re.match(r'(.*?#*){0,3}\s?(upgrayedd|upgrayed|upgraydd|upgrayydd|upgrayyedd|upgrayedd|upgreyed|upgreydd|upgreyydd|upgreyyedd)',message,re.IGNORECASE):
                logger.info(str(getframeinfo(currentframe()).lineno) + ": UPGRAYEDD message")
                web_client.reactions_add(channel=channel, name='party', timestamp=timestamp)  
                web_client.chat_postMessage( channel=channel, text="", thread_ts=evt["ts"],
                attachments='[{"title":"UPGRAYEDD","image_url":"https://pbs.twimg.com/media/E4uxqv-XwAU_Ar3.jpg"}]')
            elif re.match(r'(.*?#*){0,3}\s?(covid)',message,re.IGNORECASE):
                web_client.reactions_add(channel=channel, name='parrot-covid19', timestamp=timestamp)
            elif re.match(r'(.*?#*){0,3}\s?(trilith)',message,re.IGNORECASE):
                web_client.reactions_add(channel=channel, name='peach', timestamp=timestamp)
            elif re.match(r'(.*?#*){0,3}\s?(party)',message,re.IGNORECASE):
                logger.info(str(getframeinfo(currentframe()).lineno) + ": PARTY message")
                web_client.reactions_add(channel=channel, name='apocalyptic_danceparty', timestamp=timestamp)
            elif re.match(r'(.*?#*){0,3}\s?(goat)',message,re.IGNORECASE):
                logger.info(str(getframeinfo(currentframe()).lineno) + ": GOAT message")
                web_client.reactions_add(channel=channel, name='goat', timestamp=timestamp)
            elif re.match(r'(.*?#*){0,3}\s?(ooo|omw)',message,re.IGNORECASE):
                logger.info(str(getframeinfo(currentframe()).lineno) + ": OoO message")
                web_client.reactions_add(channel=channel, name='portal-parrot-orange', timestamp=timestamp)                        
            elif re.match(r'(.*?#*){0,3}\s?(good\smorning)',message,re.IGNORECASE):
                logger.info(str(getframeinfo(currentframe()).lineno) + ": SIGN ON message")
                web_client.reactions_add(channel=channel, name='starbucks_cup', timestamp=timestamp)
            elif re.match(r'(.*?#*){0,3}\s?(conga\ line)',message,re.IGNORECASE):
                logger.info(str(getframeinfo(currentframe()).lineno) + ": CONGA LINE message")                           
                web_client.chat_postMessage( channel=channel, text=':conga_parrot::conga_parrot::conga_parrot::conga_parrot::conga_parrot::conga_parrot::conga_parrot::conga_parrot::conga_parrot::conga_parrot::conga_parrot::conga_parrot::conga_parrot:')
            elif re.match(r'(.*?#*){0,3}\s?(!wave)',message,re.IGNORECASE):
                logger.info(str(getframeinfo(currentframe()).lineno) + ": CONGA LINE message")                           
                web_client.chat_postMessage( channel=channel, text=":parrotwave1::parrotwave2::parrotwave3::parrotwave4::parrotwave5::parrotwave6::parrotwave7::parrotwave8-99::parrotwave9:")
            elif re.match(r'.*?(ticket|incident|request|sysaid)[\s#].*?([0-9]{6})[\D.]?',message,re.IGNORECASE):
                logger.critical(str(getframeinfo(currentframe()).lineno) + ": TICKET message")
                #which type of ticket is this?
                lmessage=message.lower()
                #if lmessage.find("zayo")<0 and lmessage.find("a10")<0 and lmessage.find("juniper")<0 and lmessage.find("coresite")<0:
                check_value=lmessage.find("infoblox")+lmessage.find("zayo")+lmessage.find("a10")+lmessage.find("juniper")+lmessage.find("coresite")+lmessage.find("soho")
                if check_value>-5:
                    logger.warning(str(getframeinfo(currentframe()).lineno) + ": vendor TICKET message lmessage="+lmessage+" and find results:"+str(lmessage.find("zayo"))+" in channel: "+channel)
                    ticket=re.match(r'.*?(ticket|incident)[\s#].*?([0-9]{6,10})[\D.]?',message,re.IGNORECASE)
                    #message_back=' I need the vendor URL '+ticket.group(2)
                    message_back="Debug for tconnolly only: "+ticket.group(2)+" channel="+channel+" check_value="+str(check_value)
                    web_client.chat_postMessage( channel="DR3T92AS0", text=message_back)#send debug to T.C.
                    #https://access.redhat.com/support/cases/#/case/02696379
                else:
                    logger.critical(str(getframeinfo(currentframe()).lineno) + ": TICKET message check_value="+str(check_value))
                    ticket=re.match(r'.*?(ticket|incident)[\s#].*?([0-9]{6})[\D.]?',message,re.IGNORECASE)
                    message_back='https://disneyusa.sysaidit.com/SREdit.jsp?QuickAcess&id='+ticket.group(2)#+" check_value="+str(check_value)
                    web_client.chat_postMessage( channel=channel, text=message_back)
            else:
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": did not match any reaction-to message:\n\n")
                eprint(pprint.pformat(message))















######################### WORKFLOW OR BOT MESSAGES                   

    elif "subtype" in evt and evt["subtype"]=="bot_message": #"message" and "text" in evt and 'bot_id' in evt:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
        if "text" in evt:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": mark")
#                            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": evt="+pprint.pformat(evt))
            message=evt['text']                        
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + "###################### bot_message found.")
        if "bot_profile" in evt:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + "###################### bot_profile found.")
            bot_profile=evt['bot_profile']
            channel=evt['channel']
            if 'is_workflow_bot' in bot_profile:#==True:                                    
                eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + "###################### is_workflow_bot found.")

                if "blocks" in evt:
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found blocks")
                    for block in evt["blocks"]:
                        if "elements" in block:
                            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found outer elements")
                            for outer_element in block["elements"]:
                                if "elements" in outer_element:
                                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found inner elements")
                                    for inner_element in outer_element["elements"]:
                                        inner_type=inner_element["type"]#rich_text_section
                                        if inner_type=="user" and "user_id" in inner_element:
                                            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found inner element type of user and user_id")
                                            id=inner_element["user_id"]
                                            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": pulling user id: "+str(id))

                if "text" in evt:
                    message=evt['text']
                else:
                    message=" missed evt[text] "
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": evt="+evt)
                if id:
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": pulled id="+id+", lookup_name by id")
                    user=lookup_user(id)
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": found user: "+user['real_name'])
                do_not_send_message=0

############################ PAGER DUTY
#alert_oncall_cricital
                try:
                    if user['is_bot']==true:
                        if user['real_name']=="PagerDuty":
                            eprint(pprint.pformat(evt))
                except Exception as e:
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": pagerduty message parse failed: "+str(evt))

######################### #WORKFLOW MESSAGES                            
                if re.match(r'(.*?#*){0,3}\s?(is\soffline.|offline|gnight|gnite|peace\sout|signing\sout|signing\soff|logging\soff|logging\sout)',message,re.IGNORECASE):
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": WF SIGN OFF message")
                    bbye=['bye_boo','waveboye','panda-bye','byemickey']
                    from random import seed,random,randint
                    count=len(bbye)
                    x=randint(0,count)
                    reaction=bbye[x]
                    reaction=reaction.replace(":","")
                    web_client.reactions_add(channel=channel, name=reaction, timestamp=timestamp)
                elif re.match(r'(.*?#*){0,3}\s?(is\sonline.|signing\sin|signing\son|logging\son|logging\sin)',message,re.IGNORECASE):
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": WF SIGN ON message")
                    reaction=random_reaction()
                    #web_client.reactions_add(channel=channel, name=reaction, timestamp=timestamp)
                    if "USG0J5G3U" in evt['text']:#John MacDonald
                        web_client.reactions_add(channel=channel, name="fix-parrot", timestamp=timestamp)
                    elif "USH8YFG5R" in evt['text']:#Lance Le Roux #USH8YFG5R
                        web_client.reactions_add(channel=channel, name="lance-4450", timestamp=timestamp)
                    elif "URHKG0ALT" in evt['text']:#Tim Connolly #URHKG0ALT
                        web_client.reactions_add(channel=channel, name="tim_connolly_hockey", timestamp=timestamp)
                    elif "USJGXHW3T" in evt['text']:#Ricardo Vargas #USJGXHW3T
                        web_client.reactions_add(channel=channel, name="facepalm", timestamp=timestamp)       #superman-5821  #ricardo_vargas                          
                elif re.match(r'(.*?#*){0,3}\s?(has\scompleted|is\sdone)',message,re.IGNORECASE):
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": WF CHANGE COMPLETE message")
                    web_client.reactions_add(channel=channel, name='cookie', timestamp=timestamp)  
                elif re.match(r'(.*?#*){0,3}\s?(is\sdone|clicked\sChange\sCompleted)',message,re.IGNORECASE):
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": WF IS DONE message")
                    web_client.reactions_add(channel=channel, name='cookie', timestamp=timestamp)                          
                elif re.match(r'(.*?#*){0,3}\s?(is\son\slunch\sbreak.|lunch\stest)',message,re.IGNORECASE):
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": WF LUNCH BREAK message")
                    lunch_responses=['hamburgerdance','dancing_hotdog','taco','burrito']
                    import random
                    random_lunch_choice=random.choice(lunch_responses)
                    web_client.reactions_add(channel=channel, name=random_lunch_choice, timestamp=timestamp)
                elif re.match(r'(.*?#*){0,3}\s?(teams\sissue)',message,re.IGNORECASE):
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": TEAMS ISSUE message")
                    web_client.reactions_add(channel=channel, name='walledlp', timestamp=timestamp)
                    output="This IS the link you are looking for: https://portal.office.com/servicestatus"
                    web_client.chat_postMessage( channel=channel, text=output, thread_ts=evt["ts"])                      
                elif re.match(r'(.*?#*){0,3}\s?(is\sdeploying\schange)',message,re.IGNORECASE):
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": WF CHANGE message")
                    web_client.reactions_add(channel=channel, name='four_leaf_clover', timestamp=timestamp)
#Route-Switch Minor Changes                                    
                    url="https://twdc.webhook.office.com/webhookb2/8eb076d6-8b53-46a4-9d08-e92e70f8af36@56b731a8-a2ac-4c32-bf6b-616810e913c6/IncomingWebhook/625eea8cd236459eace33ee360acedda/5f3fd977-663e-4468-a46f-6ba7ae4ecf65"
                    output=user['real_name']+": "+str(message)
                    data={"text":output}
                    post(url,'',data)              
                elif re.match(r'(.*?#*){0,3}\s?(using\sreference)',message,re.IGNORECASE):
                    try:
                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": WF FW CHANGE message")
                        web_client.reactions_add(channel=channel, name='four_leaf_clover', timestamp=timestamp)
    #Route-Switch Minor Changes                                    
                        url="https://twdc.webhook.office.com/webhookb2/8eb076d6-8b53-46a4-9d08-e92e70f8af36@56b731a8-a2ac-4c32-bf6b-616810e913c6/IncomingWebhook/625eea8cd236459eace33ee360acedda/5f3fd977-663e-4468-a46f-6ba7ae4ecf65"
                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) +": message="+str(message))

                        pattern='<@[A-Z]*>'
                        x=re.search(r'[a-zA-Z0-9.\s]*(<@[A-Z]*>)[a-zA-Z0-9.\s]*',message,re.IGNORECASE)
                        user=lookup_user(x.group(1).strip("<@>"))
                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": looked up user: "+user['real_name'])
                        repl=user["real_name"]
                        output=re.sub(pattern, repl, message, count=0, flags=0)

                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": POSTING TO TEAMS 'Route-Switch Minor Changes' channel:\n"+output)
                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) +": about to post")
#                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + pprint.pformat(post(url=url,data={"text":output})))
                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) +": post successful")                          
                    except Exception as e:
                        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) +": post failed - "+str(e))
                elif bot_profile['text'] != 'Personal Status':
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + pprint.pformat(evt))
#'text': '<@URHKG0ALT> has completed short',
                    user=lookup_user(message.split(" ")[0])
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + pprint.pformat(user))
                    output=user['profile']['display_name_normalized']+": "+message.split(' ', 1)[1]
                    #url='https://outlook.office.com/webhook/6b929718-224d-44b0-9d2e-c62d380d2ff0@56b731a8-a2ac-4c32-bf6b-616810e913c6/IncomingWebhook/a3e03cfc0e474272a44f036de4968cf1/5f3fd977-663e-4468-a46f-6ba7ae4ecf65' # Networking Teams channel
                    url='https://twdc.webhook.office.com/webhookb2/6b929718-224d-44b0-9d2e-c62d380d2ff0@56b731a8-a2ac-4c32-bf6b-616810e913c6/IncomingWebhook/4d0ef6b411a047e0bb5643116f8c24d6/5f3fd977-663e-4468-a46f-6ba7ae4ecf65' # Networking Events Teams Channel
                    data={"text":output}
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) +": mark")
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + pprint.pformat(post(url=url,data=data)))
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) +": mark")
                else:
                    logger.error(str(getframeinfo(currentframe()).lineno) + ": " + "###################### Unknown Workflow found. " +str(evt))                                        
                    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + pprint.pformat(evt))


## END OF NEW FUNCTIONS
#############################################################################################################################                            
        elif message.startswith("!"):
            #web_client.chat_postMessage( channel=channel, text=str(getframeinfo(currentframe()).lineno) + "::unknown command - type !help if you need it: " + message,timestamp=timestamp,thread_ts=evt["ts"])
            web_client.reactions_add(channel=channel, name='question', timestamp=timestamp)
        else:
            eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": hit bottom of conditionals on message: " +pprint.pformat(evt))


#######################################
    else:
        eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": " + "###################### Unknown event found: " +pprint.pformat(evt))

#######################################



#Accountable, Responsible, Consulted and Informed
########################################################## END OF MAIN ###########################
@RTMClient.run_on(event='accounts_changed')
def accounts_changed(**payload):
    eprint('event type: accounts_changed')

@RTMClient.run_on(event='bot_added')
def bot_added(**payload):
    eprint('event type: bot_added')

@RTMClient.run_on(event='bot_changed')
def bot_changed(**payload):
    eprint('event type: bot_changed')

@RTMClient.run_on(event='channel_archive')
def channel_archive(**payload):
    eprint('event type: channel_archive')

@RTMClient.run_on(event='channel_created')
def channel_created(**payload):
    eprint('event type: channel_created')

@RTMClient.run_on(event='channel_deleted')
def channel_deleted(**payload):
    eprint('event type: channel_deleted')

@RTMClient.run_on(event='channel_history_changed')
def channel_history_changed(**payload):
    eprint('event type: channel_history_changed')

@RTMClient.run_on(event='channel_joined')
def channel_joined(**payload):
    eprint('event type: channel_joined')

@RTMClient.run_on(event='channel_left')
def channel_left(**payload):
    eprint('event type: channel_left')

@RTMClient.run_on(event='channel_marked')
def channel_marked(**payload):
    eprint('event type: channel_marked')

@RTMClient.run_on(event='channel_rename')
def channel_rename(**payload):
    eprint('event type: channel_rename')

@RTMClient.run_on(event='channel_unarchive')
def channel_unarchive(**payload):
    eprint('event type: channel_unarchive')

@RTMClient.run_on(event='commands_changed')
def commands_changed(**payload):
    eprint('event type: commands_changed')

@RTMClient.run_on(event='dnd_updated')
def dnd_updated(**payload):
    global debug
    if debug > 40:
        eprint('event type: dnd_updated')

@RTMClient.run_on(event='dnd_updated_user')
def dnd_updated_user(**payload):
    global debug
    if debug > 40:
        eprint('event type: dnd_updated_user')

@RTMClient.run_on(event='email_domain_changed')
def email_domain_changed(**payload):
    eprint('event type: email_domain_changed')

@RTMClient.run_on(event='emoji_changed')
def emoji_changed(**payload):
    eprint('event type: emoji_changed')

@RTMClient.run_on(event='external_org_migration_finished')
def external_org_migration_finished(**payload):
    eprint('event type: external_org_migration_finished')

@RTMClient.run_on(event='external_org_migration_started')
def external_org_migration_started(**payload):
    eprint('event type: external_org_migration_started')

@RTMClient.run_on(event='file_change')
def file_change(**payload):
    eprint('event type: file_change')

@RTMClient.run_on(event='file_comment_added')
def file_comment_added(**payload):
    eprint('event type: file_comment_added')

@RTMClient.run_on(event='file_comment_deleted')
def file_comment_deleted(**payload):
    eprint('event type: file_comment_deleted')

@RTMClient.run_on(event='file_comment_edited')
def file_comment_edited(**payload):
    eprint('event type: file_comment_edited')

@RTMClient.run_on(event='file_created')
def file_created(**payload):
    eprint('event type: file_created')

@RTMClient.run_on(event='file_public')
def file_public(**payload):
    eprint('event type: file_public')

@RTMClient.run_on(event='file_shared')
def file_shared(**payload):
    eprint('event type: file_shared')

@RTMClient.run_on(event='file_unshared')
def file_unshared(**payload):
    eprint('event type: file_unshared')

@RTMClient.run_on(event='goodbye')
def goodbye(**payload):
    eprint('event type: goodbye')

@RTMClient.run_on(event='group_archive')
def group_archive(**payload):
    eprint('event type: group_archive')

@RTMClient.run_on(event='group_close')
def group_close(**payload):
    eprint('event type: group_close')

@RTMClient.run_on(event='group_deleted')
def group_deleted(**payload):
    eprint('event type: group_deleted')

@RTMClient.run_on(event='group_history_changed')
def group_history_changed(**payload):
    eprint('event type: group_history_changed')

@RTMClient.run_on(event='group_joined')
def group_joined(**payload):
    eprint('event type: group_joined')

@RTMClient.run_on(event='group_left')
def group_left(**payload):
    eprint('event type: group_left')

@RTMClient.run_on(event='group_marked')
def group_marked(**payload):
    eprint('event type: group_marked')

@RTMClient.run_on(event='group_open')
def group_open(**payload):
    eprint('event type: group_open')

@RTMClient.run_on(event='group_rename')
def group_rename(**payload):
    eprint('event type: group_rename')

@RTMClient.run_on(event='group_unarchive')
def group_unarchive(**payload):
    eprint('event type: group_unarchive')

@RTMClient.run_on(event='hello')
def hello(**payload):
    eprint('event type: hello')

@RTMClient.run_on(event='im_close')
def im_close(**payload):
    eprint('event type: im_close')

@RTMClient.run_on(event='im_created')
def im_created(**payload):
    eprint('event type: im_created')

@RTMClient.run_on(event='im_history_changed')
def im_history_changed(**payload):
    eprint('event type: im_history_changed')

@RTMClient.run_on(event='im_marked')
def im_marked(**payload):
    eprint('event type: im_marked')

@RTMClient.run_on(event='im_open')
def im_open(**payload):
    eprint('event type: im_open')

@RTMClient.run_on(event='manual_presence_change')
def manual_presence_change(**payload):
    eprint('event type: manual_presence_change')

@RTMClient.run_on(event='member_joined_channel')
def member_joined_channel(**payload):
    eprint('event type: member_joined_channel')

@RTMClient.run_on(event='member_left_channel')
def member_left_channel(**payload):
    eprint('event type: member_left_channel')

@RTMClient.run_on(event='pin_added')
def pin_added(**payload):
    eprint('event type: pin_added')

@RTMClient.run_on(event='pin_removed')
def pin_removed(**payload):
    eprint('event type: pin_removed')

@RTMClient.run_on(event='pref_change')
def pref_change(**payload):
    eprint('event type: pref_change')

@RTMClient.run_on(event='presence_change')
def presence_change(**payload):
    eprint('event type: presence_change')

@RTMClient.run_on(event='presence_query')
def presence_query(**payload):
    eprint('event type: presence_query')

@RTMClient.run_on(event='presence_sub')
def presence_sub(**payload):
    eprint('event type: presence_sub')

@RTMClient.run_on(event='reaction_added')
def reaction_added(**payload):
    eprint('event type: reaction_added')

@RTMClient.run_on(event='reaction_removed')
def reaction_removed(**payload):
    eprint('event type: reaction_removed')

@RTMClient.run_on(event='reconnect_url')
def reconnect_url(**payload):
    eprint('event type: reconnect_url')

@RTMClient.run_on(event='shared_channel_invite_received')
def shared_channel_invite_received(**payload):
    eprint('event type: shared_channel_invite_received')

@RTMClient.run_on(event='star_added')
def star_added(**payload):
    eprint('event type: star_added')

@RTMClient.run_on(event='star_removed')
def star_removed(**payload):
    eprint('event type: star_removed')

@RTMClient.run_on(event='subteam_created')
def subteam_created(**payload):
    eprint('event type: subteam_created')

@RTMClient.run_on(event='subteam_members_changed')
def subteam_members_changed(**payload):
    eprint('event type: subteam_members_changed')

@RTMClient.run_on(event='subteam_self_added')
def subteam_self_added(**payload):
    eprint('event type: subteam_self_added')

@RTMClient.run_on(event='subteam_self_removed')
def subteam_self_removed(**payload):
    eprint('event type: subteam_self_removed')

@RTMClient.run_on(event='subteam_updated')
def subteam_updated(**payload):
    eprint('event type: subteam_updated')

@RTMClient.run_on(event='team_domain_change')
def team_domain_change(**payload):
    eprint('event type: team_domain_change')

@RTMClient.run_on(event='team_join')
def team_join(**payload):
    eprint('event type: team_join')
    global channelsinfo
    data = payload['data']
    with open(str(getframeinfo(currentframe()).function)+".json", 'w') as outfile:
        json.dump(data, outfile)
    web_client = payload['web_client']

@RTMClient.run_on(event='team_migration_started')
def team_migration_started(**payload):
    eprint('event type: team_migration_started')

@RTMClient.run_on(event='team_plan_change')
def team_plan_change(**payload):
    eprint('event type: team_plan_change')

@RTMClient.run_on(event='team_pref_change')
def team_pref_change(**payload):
    eprint('event type: team_pref_change')

@RTMClient.run_on(event='team_profile_change')
def team_profile_change(**payload):
    eprint('event type: team_profile_change')

@RTMClient.run_on(event='team_profile_delete')
def team_profile_delete(**payload):
    eprint('event type: team_profile_delete')

@RTMClient.run_on(event='team_profile_reorder')
def team_profile_reorder(**payload):
    eprint('event type: team_profile_reorder')

@RTMClient.run_on(event='team_rename')
def team_rename(**payload):
    eprint('event type: team_rename')

@RTMClient.run_on(event='file_deleted')
def message(**file_deleted):
    global debug
    if debug > 40:
        eprint('event type: file_deleted')
        eprint(str(getframeinfo(currentframe()).function)+" "+str(getframeinfo(currentframe()).lineno) + " "+pprint.pformat(file_deleted))

@RTMClient.run_on(event='user_change')
def message(**user_change):
    global debug
    if debug > 40:
        eprint('event type: user_change')
        logger.debug(pprint.pformat(user_change))
        data=user_change['data']
        user=data['user']
        enterprise=user['enterprise_user']
        profile=user['profile']
        try:
            eprint(enterprise['enterprise_name']+": "+user['real_name']+" ("+profile['email']+") "+profile['title']+" in the "+user['tz']+" timezone.")
        except Exception as e:
            eprint(str(getframeinfo(currentframe()).function)+" "+str(getframeinfo(currentframe()).lineno) + " exception: "+str(e))    

@RTMClient.run_on(event='user_huddle_changed')
def message(**payload):
    global debug
    if debug > 40:
        eprint('event type: user_huddle_changed')
        logger.debug(pprint.pformat(payload))
        data=payload['data']
        user=data['user']
    #    enterprise=user['enterprise_user']
        profile=user['profile']
        try:
            eprint(profile['real_name']+" ("+profile['email']+") ")# +profile['title']+" "+profile['status_text']+" in the "+user['tz']+" timezone.")
        except Exception as e:
            eprint(str(getframeinfo(currentframe()).function)+" "+str(getframeinfo(currentframe()).lineno) + " exception: "+str(e))    


@RTMClient.run_on(event='user_profile_changed')
def message(**payload):
    global debug
    if debug > 40:
        eprint('event type: user_profile_changed')
        logger.debug(pprint.pformat(payload))
        data=payload['data']
        user=data['user']
        enterprise=user['enterprise_user']
        profile=user['profile']
        try:
            eprint(enterprise['enterprise_name']+": "+user['real_name']+" ("+profile['email']+") "+profile['title']+" in the "+user['tz']+" timezone.")
        except Exception as e:
            eprint(str(getframeinfo(currentframe()).function)+" "+str(getframeinfo(currentframe()).lineno) + " exception: "+str(e))    

@RTMClient.run_on(event='user_status_changed')
def message(**payload):
    global debug
    if debug > 40:
        eprint('event type: user_status_changed')
        logger.debug(pprint.pformat(payload))
        data=payload['data']
        user=data['user']
        enterprise=user['enterprise_user']
        profile=user['profile']
        try:
            eprint(enterprise['enterprise_name']+": "+user['real_name']+" ("+profile['email']+") "+profile['title']+" in the "+user['tz']+" timezone.")
        except Exception as e:
            eprint(str(getframeinfo(currentframe()).function)+" "+str(getframeinfo(currentframe()).lineno) + " exception: "+str(e))
        
@RTMClient.run_on(event='user_typing') # ("{'data': {'channel': 'DR3T92AS0', 'user': 'URHKG0ALT'},\n"
def message(**payload):
    global debug
    if debug > 40:
        eprint('event type: user_typing')
        logger.debug(pprint.pformat(payload))
        data=payload['data']
        user_id=data['user']
        channel_id=data['channel']
        channel_info=lookup_channel(channel_id)
        user=lookup_user(user_id)
        enterprise=user['enterprise_user']
        profile=user['profile']
        try:
            eprint(enterprise['enterprise_name']+": "+user['real_name']+" ("+profile['email']+") "+profile['title']+" in the "+user['tz']+" timezone.")
        except Exception as e:
            eprint(str(getframeinfo(currentframe()).function)+" "+str(getframeinfo(currentframe()).lineno) + " exception: "+str(e))
            eprint(user)







def post(url='',mods='',data={}):
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": post "+str(data))
#    data=data.strip('"')

#   Replace user with real_name and maybe a link to profile?

    http = urllib3.PoolManager()
    resp = http.request('POST', url, body=data, headers={'Content-Type': 'application/json'})
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno) + ": done posting")
    return resp.data.decode('utf-8')


    #req="https://" + api_auth.api_hostname + url
#    if mods:#needs tested
#        req+="?" + mods
#   response=requests.post(url,json=data,verify=False)
#    if response.status_code == 200:
#        try:
#            return response.json()
#        except ValueError:
#            return response.text
#    else:
#        response.raise_for_status()
#        return response.json()        
######################################################### FLASK APPS ###########################
#@app.route("/get", methods=['GET'])

@app.route("/hello") # health checker
def hello():
    return "<beep boop, bepeety boop>"
    

@app.route("/reconnect")
def flask_reconnect():
    if sc.rtm_connect(auto_reconnect=True):
        return "Connected!"
    else:
        return "Not reconnected."



@app.route("/usersinfo")
def flask_user_list():
    global running_in_openshift,usersinfo_filename

    with open(usersinfo_filename, 'r') as outfile:
        return pprint.pformat(outfile.read())
    return 

@app.route("/site-map")
def list_routes():
    import urllib
    output = []
    for rule in app.url_map.iter_rules():

        options = {}
        for arg in rule.arguments:
            options[arg] = "[{0}]".format(arg)

        methods = ','.join(rule.methods)
        url = flask.url_for(rule.endpoint, **options)
        line = urllib.parse.unquote("{:50s} {:20s} {}".format(rule.endpoint, methods, url))
        output.append(line)
    return jsonify(output)

@app.route("/os_environ")
def os_environ():
    return jsonify(pprint.pformat(os.environ))

@app.route("/")
def flask_root():
    return render_template('table_index.html',title='Slackbot',content="The sysaid_slackbot")


@app.errorhandler(404)
def page_not_found(e):
    #if re.findall(r'localhost',flask.request.host):
        #return flask.Response('',301,{'location':'https://spn-vpn-autoprov.us-west-2.ocp.studio.disney.com/'+'/site-map'})
    return "<h1>404</h1><p>The resource could not be found.</p>Try using the site-map: <a href=/site-map>Site-Map</a>", 404
########################################################## FORK MAIN #############################
if 0:#to fork or not to fork
    newpid = os.fork()
    if newpid == 0:
        while 1:
            main()
            logger.error(str(getframeinfo(currentframe()).lineno) + ": exited out of main")
            time.sleep(1)
            exit()
    else:
        pids = (os.getpid(), newpid)
        eprint("parent: %d, child: %d\n" % pids)

########################################################## END OF MAIN ###########################
def goodbye():
    global start_time,newpid
    pids = [newpid]
    eprint("Ran for "+str(time.time() - start_time)+" seconds.")
    timeout_sec = 5
    for pid in pids: # list of your processes
    #if 1:
        p_sec = 0
        for second in range(timeout_sec):
            if pid.poll() == None:
                time.sleep(1)
                p_sec += 1
        if p_sec >= timeout_sec:
            logging.warning(str(getframeinfo(currentframe()).lineno) + " pid "+str(pid)+" killed")
            p.kill() # supported from python 2.6
    
    exit(getframeinfo(currentframe()).lineno)

def good_morning(channel="G01074YHFG9"):#studio-network-team"):#"#spn-wall-e-control-channel"):#DR3T92AS0"):#DR3T92AS0,Tim direct: "DR3T92AS0"
    day_of_week=datetime.datetime.today().strftime('%A')
    web_client.chat_postMessage( channel=channel, text="Happy "+day_of_week+"!!")#,attachments='[{"title":"Email Grooming","image_url":"https://dccr.disney.com/html/email/newsreel/digest/20210923/newsreel_digest_img_feature07.png"}]') 
#example    web_client.chat_postMessage(channel='D0K7P9MCJ', text='postMessage test',attachments='[{"image_url":"http://i.ytimg.com/vi/tntOCGkgt98/maxresdefault.jpg"}]')        

#https://dccr.disney.com/html/email/newsreel/digest/20210923/newsreel_digest_img_feature07.png    
    time_clock(channel)

@app.route("/stop")
def stop_rtm():
    eprint("stopping rtm_client")
    message=str(getframeinfo(currentframe()).lineno)+": "+botname+" is stopping on " + myhostname
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+": rtm_client about to stop")
    rtm_client.stop()
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+": rtm_client has been stopped")    

@app.route("/start")
def start_rtm():
    eprint("starting rtm_client")
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+": rtm_client about to start")
    rtm_client.start()
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+": rtm_client has been run")

############################################################################################################################## END OF ROUTES

from apscheduler.schedulers.background import BackgroundScheduler
import time,atexit,sys
NYC = zoneinfo.ZoneInfo("America/New_York")
tz=time.tzname
#logging.warning("Scheduler now running, time zone: "+tz[0])
tzhour=0
if tz[0]=='UTC':
    tzhour=7#UTC offset normalized
#if not app.debug:
if 1:
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=version_check, trigger="interval", seconds=5)

#    if auth_test not in scheduler.get_jobs():
#        logging.warning(str(getframeinfo(currentframe()).lineno) + ": auth_test added to schedule")
#        scheduler.add_job(func=limit_presence_check, trigger="interval", seconds=120)
    scheduler.add_job(time_clock, 'cron', day_of_week='mon-fri', hour=tzhour+7, minute=57)#day_of_week='mon-sat',7am
#    scheduler.add_job(time_clock, trigger="interval", seconds=20)
#    else:
#        logging.warn("Scheduler dupe")
    #scheduler.add_job(func=main)
    scheduler.start()
    # Shut down the scheduler when exiting the app
    ############################################################### needs fixed atexit.register(lambda: goodbye())
    atexit.register(lambda: scheduler.shutdown())
    #atexit.register(time_clock,'#DR3T92AS0'))
    logger.error(str(getframeinfo(currentframe()).lineno) + ": exited out of scheduler setup - normal")
######### SCHEDULER SETUP ############### END

if not running_in_openshift:
    import atexit
    #defining function to run on shutdown
    def on_exit_update_version():
        return str(version)
    #Register the function to be called on exit
    atexit.register(on_exit_update_version)

if 0:
    newpid = os.fork()
    if newpid == 0:
        childpid=str(os.getpid())
        while 1:
            main()
            logger.error(str(getframeinfo(currentframe()).lineno) + ": exited out of main")
            time.sleep(1)
            #logger.error("Child has finished "+childpid)
            os._exit(0)
            sys.exit(0)
    else:
        pids = (os.getpid(), newpid)
        eprint("parent: %d, child: %d\n" % pids)

def send_message(channel='',text=' send_message test'):
    global sc
    sc.chat_postMessage(channel=status_channel,text=str(getframeinfo(currentframe()).lineno) + text)
#send_message("G01074YHFG9",str(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno))+": test")

if 0: #__name__ == "__main__":
    eprint("found myself in __main__")
    app.config['DEBUG']=False
    app.run(port=tcp_port,host='0.0.0.0')
else:
    eprint(str(getframeinfo(currentframe()).lineno) + ": found myself outside of __main__")
    app.config['DEBUG']=False
    logger.error(str(getframeinfo(currentframe()).lineno) + ": " + "__name__="+__name__)

################################################################################################################




if os.environ['APP_ENV']==running_environment:
    eprint("starting rtm_client")
    message=str(getframeinfo(currentframe()).lineno)+": "+botname+" is running on " + myhostname
#    rtm=RTMClient(token=token)
#    sc = slack_sdk.WebClient(token=token)
#    sc.chat_postMessage(channel=status_channel,text=message) # {"channel":status_channel, "text":message}) 
    #RTMClient.api_call("chat_postMessage", channel=status_channel, text=str(getframeinfo(currentframe()).lineno) + ": "+message)
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+": rtm_client about to start")
    rtm_client.start()
    eprint(getframeinfo(currentframe()).function+"::"+str(getframeinfo(currentframe()).lineno)+": rtm_client has been run")
else:
    eprint("Skipping execution since "+running_environment+" != "+os.environ['APP_ENV'])

if 0: #__name__ == "__main__":
    eprint("starting flask")
    app.config['DEBUG']=False
    app.run(port=tcp_port,host='0.0.0.0')

eprint("EXITING - EOF")



