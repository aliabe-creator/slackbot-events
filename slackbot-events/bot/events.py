'''
Created on Jul 13, 2021

@author: Private

'''

import slack
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
import json
from googleapiclient.discovery import build
import google_auth_oauthlib.flow
from datetime import datetime, timedelta, date, time
import base64
import pprint
import re
from dotenv import load_dotenv
import os
from multiprocessing import Process

load_dotenv()

signing = os.environ.get("signing")
slack_token = os.environ.get("slack")
client_secrets_file = 'calsecret.json'

app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(signing, '/slack/events', app)
client = slack.WebClient(token = slack_token)

SCOPES = ['https://www.googleapis.com/auth/calendar']
flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
client_secrets_file, SCOPES)
credentials = flow.run_console()
service = build('calendar', 'v3', credentials=credentials)

bot_id = client.api_call("auth.test")['user_id']

client.conversations_open(users='U01EJSDGX50')
client.chat_postMessage(channel='D0280FPSM5M', text='Bot is now online!') #UPDATE THIS!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

channel_id = '' #needed for use in other functions
event_name = '' #global variable to use for storing event name
selected_date = ''
selected_time = ''
full_location = ''
gcal_link = ''

authed_admins = ['U01EJSDGX50', 'U01FXTVV09K', 'U01BTFNENPQ', 'U01G9S2P6CV', 'U01GN01N881', 'U01C6DC5HTN']

@app.route('/slack/postevent', methods=['POST'])
def peven():
    p_data = request.form
    p_user_id = p_data.get('user_id') # implement restrictions on who can use
    p_channel_id = p_data.get('channel_id')
    p_text = p_data.get('text')
    
    if (p_user_id in authed_admins): #ensure person is actually an admin
        if (p_text != ''): #ensures that there is actually text
            if ('eventedit' in p_text):
                client.chat_postEphemeral(user = p_user_id, channel = p_channel_id, text = 'Be careful! This command will post the event WITHOUT any confirmation.')
                
                client.chat_postMessage(channel = p_channel_id, blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Specified Event URL:* " + p_text
                        }
                    }
                ])
                
                event_id = p_text.partition("eventedit/")[2] #get the base64 string
                id_b = event_id.encode('utf-8') #encode base64 string to binary
                decode = base64.b64decode(id_b + b'==') #decode to normal string, adding placeholder
                id_pretruncate = str(decode.split()[0]) #get only the event id part
                
                final_id = id_pretruncate[2:len(id_pretruncate)-1] #truncate b' and ' from string to get final id
                
                #query API for event details
                event = service.events().get(calendarId='primary', eventId=final_id).execute()
                pprint.pprint(event)
                
                location = event.get('location')
                description = event.get('description')
                recurrence = event.get('recurrence')
                
                if (event.get('recurringEventId') is not None):
                    recurrId = event.get('recurringEventId')
                    eventr = service.events().get(calendarId='primary', eventId=recurrId).execute()
                    recurrence = eventr.get('recurrence')
                
                postFinalMessage(event['summary'], description, location, recurrence, event['start']['dateTime'].partition("T")[0], re.search('T(.*)-', event['start']['dateTime']).group(1), event['htmlLink'])
            
            else: #meaning posted an invalid link
                client.chat_postEphemeral(user = p_user_id, channel = p_channel_id, text='Please post a link in the format: https://calendar.google.com/calendar/u/1/r/eventedit/...')
        else:
            #posts ephermal message reminding the user to supply args
            client.chat_postEphemeral(user = p_user_id, channel = p_channel_id, text='You seem to have forgotten some args!')
        
        return Response(), 200
    
    else: #if user is not an admin
        client.chat_postEphemeral(user = p_user_id, channel = p_channel_id, text='You are not authorized to use this command. If this seems like a mistake, DM an admin.')
        
@app.route('/slack/addevent', methods=['POST'])
def add():
    global event_name #required to ensure event_name is global
    global channel_id
    
    data = request.form
    user_id = data.get('user_id') # ~implement restrictions on who can use
    channel_id = data.get('channel_id')
    text = data.get('text')
    
    if (user_id in authed_admins):
        if (text != ''): #ensures that there is actually text
            event_name = text #set event name
            client.chat_postMessage(channel = channel_id, blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Specified Event Name:* " + event_name
                    }
                }
            ])
            
            #next, post datepicker
            client.chat_postMessage(channel=channel_id, blocks=[
                {
                    "type": "section",
                    "block_id": "dateselector",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Pick a date for the event.*"
                    },
                    "accessory": {
                        "type": "datepicker",
                        "action_id": "pickdate",
                        "initial_date": str(datetime.now())[0:10], #later set this to today
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a date"
                        }
                    }
                }
            ])
            
        else:
            #posts ephermal message reminding the user to supply args
            client.chat_postEphemeral(user = user_id, channel = channel_id, text='You seem to have forgotten some args!')
        
        return Response(), 200
    
    else:
        client.chat_postEphemeral(user = user_id, channel = channel_id, text='You are not authorized to use this command. If this seems like a mistake, DM an admin.')
        
@app.route('/slack/block', methods=['POST'])
def block(): #for any block action
    global selected_date #required to globalize selected time'
    global selected_time
    global full_location
    
    data = request.form
    raw = data.get('payload') #get only payload json
    payload = json.loads(raw)
    block_type = payload['actions'][0]['type']
    
    if (block_type == 'datepicker'): #got date
        selected_date = payload['actions'][0]['selected_date']
        
        #timepicker: MAKE SURE TO ENABLE BETA FEATURES IN SLACK APP!
        client.chat_postMessage(channel=channel_id, blocks=[
            {
                "type": "section",
                "block_id": "section1234",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Pick a time of day for the event.*"
                },
                "accessory": {
                    "type": "timepicker",
                    "action_id": "picktime",
                    "initial_time": "12:00",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a time"
                    }
                }
            }
        ])
    
    if (block_type == 'timepicker'): #get time
        selected_time = payload['actions'][0]['selected_time']
        
        client.chat_postMessage(channel=channel_id, blocks=[ #send the input block for location
                {
                    "dispatch_action": True,
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "fuzzy_loc"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Location of event:",
                        "emoji": True
                    }
                }
            ])
                                                            
    if (block_type == 'plain_text_input'):
        if (payload['actions'][0]['action_id'] == 'fuzzy_loc'): #if this text input is for loc search
            location = payload['actions'][0]['value'] #save location to a var
            formatted_location = location.replace(' ', '+') #format location to append to gmaps
            link = 'https://www.google.com/maps/search/' + formatted_location
            
            #give user the link to look for full address to paste
            client.chat_postMessage(channel=channel_id, text='Use the below link to find the full address of your location, copy and paste it below: \n' + link)
            
            #post next box for user to paste in full loc
            client.chat_postMessage(channel=channel_id, blocks=[ #send the input block for location
                {
                    "dispatch_action": True,
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "full_loc"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Paste in full address of event:",
                        "emoji": True
                    }
                }
            ])
        
        if (payload['actions'][0]['action_id'] == 'full_loc'): #this means that action_id = 'full_loc'
            full_location = payload['actions'][0]['value']
            
            #final ask for publish
            client.chat_postMessage(channel=channel_id, blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Publish event?",
                        "emoji": True
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Cancel",
                                "emoji": True
                            },
                            "value": "click_me_123",
                            "action_id": "cancel",
                            "style": "danger"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Publish",
                                "emoji": True
                            },
                            "value": "click_me_123",
                            "action_id": "submit",
                            "style": "primary"
                        }
                    ]
                }
            ])
        
    if (block_type == 'button'): #so far, only used for final confirmation
        if (payload['actions'][0]['action_id'] == 'cancel'):
            client.chat_postMessage(channel=channel_id, text='Quitting Add Event Wizard...')
            reset()
            return Response(), 200 #should terminate the program
        if (payload['actions'][0]['action_id'] == 'submit'):
            genCalLink(event_name, full_location, selected_date, selected_time) #proceed, pass to helper func

    return Response(), 200

def genCalLink(name, location, date, time):
    global gcal_link
    
    time_object = datetime.strptime(time, '%H:%M') #parse to datetime object
    offset = time_object + timedelta(hours=2) #offset by 2 hours
    endtime = str(offset.time())[0:8]
        
    event = {
      'summary': name,
      'location': location,
      'start': {
        'dateTime': str(date + 'T' + time + ':00.000'),
        'timeZone': 'America/Los_Angeles',
      },
      'end': {
        'dateTime': date + 'T' + endtime,
        'timeZone': 'America/Los_Angeles',
      },
      'reminders': {
        'useDefault': False,
        'overrides': [
          {'method': 'email', 'minutes': 24 * 60},
          {'method': 'popup', 'minutes': 30},
        ],
      },
    }
    
    try:
        event = service.events().insert(calendarId='primary', body=event).execute()
        gcal_link = event.get('htmlLink')
        
        postFinalMessage(name, None, location, None, date, time, gcal_link) #helper function to get everything posted
    
    except Exception as e:
        client.chat_postMessage(channel='D0280FPSM5M', text='Failed in updating calendar. \n' + str(e))
        reset()

def postFinalMessage(name, description, location, recurrence, date, starttime, link):
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": name,
                "emoji": True
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":calendar: *Date (YYYY-MM-DD):* " + date
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":watch: *Time: (24H, PST/PDT)* " + starttime
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":link: *Link to Event*"
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Google Calendar",
                    "emoji": True
                },
                "value": "click_me_123",
                "url": link,
                "action_id": "event_link"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":white_check_mark: *Link to official calendar:*"
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Subscribe",
                    "emoji": True
                },
                "value": "click_me_123",
                "url": "https://calendar.google.com/calendar/u/1?cid=dWNsYS5zbHBAZ21haWwuY29t",
                "action_id": "subscribe_calendar"
            }
        }
    ]
    
    if (location is not None):
        blocks.insert(4, {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":placard: *Location:* " + location
                        }
                    },)
    
    if (description is not None):
        blocks.insert(1, {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": description
                            }
                        ]
                    },)
    
    if (recurrence is not None):
        blocks.insert(5, {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": ":arrows_counterclockwise: *Recurrence rules:* " + str(recurrence)
                            }
                        },)
        
    client.chat_postMessage(channel='C01CCS7EDJM', blocks=blocks) #Send the final, formatted block
    reset()

def reset(): #resets all globals
    channel_id = ''
    event_name = ''
    selected_date = ''
    selected_time = ''
    full_location = ''
    gcal_link = ''

def remindAdmin():
    while(True):
        with open('time.json', 'r') as f:
            data = json.load(f)
            datetime_time = datetime.fromtimestamp(data['latest_scheduled'])
            seconds_since = (datetime.now() - datetime_time).total_seconds() #get seconds between now and latest scheduled message post time
            f.close()
        
            if (seconds_since > 60): # meaning the message has already been posted, need to sched a new message
                client.chat_postMessage(channel = 'D0280FPSM5M', text = 'Scheduling next admin meeting in 2 weeks.')
                
                next_date = date.today() + timedelta(days=14) #get time 14 days in advance, at 5:50 PM
                scheduled_time = time(hour=17, minute=50)
                schedule_timestamp = datetime.combine(next_date, scheduled_time).timestamp()
                
                channel_id = "G01CSM59W74" #post message
                client.chat_scheduleMessage(
                    channel=channel_id,
                    text="Admin meeting in 10 minutes!",
                    post_at=schedule_timestamp
                )
                
                with open('time.json', 'w') as f:
                    data = json.load(f)
                    data['latest_scheduled'] = schedule_timestamp #update with new latest timestamp
                    json.dump(data, f) #dump to time.json
                    f.close()
        
        time.sleep(600) #run every 10 mins
  
if __name__ == "__main__":
    p = Process(target=remindAdmin, args=()) #uses multiprocessing so that it can run concurrently!
    p.start()
    app.run(debug=True, use_reloader = False)
    p.join()