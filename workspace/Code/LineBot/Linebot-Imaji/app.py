# -*- coding: utf-8 -*-

#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import datetime
import errno
import json
import os
import sys
import tempfile
from argparse import ArgumentParser
import time
from PIL import Image
import pickle
import torch
from diffusers import StableDiffusionPipeline
from huggingface_hub import notebook_login
from datetime import datetime

from flask import Flask, request, abort, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    LineBotApiError, InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    SourceUser, SourceGroup, SourceRoom,
    TemplateSendMessage, ConfirmTemplate, MessageAction,
    ButtonsTemplate, ImageCarouselTemplate, ImageCarouselColumn, URIAction,
    PostbackAction, DatetimePickerAction,
    CameraAction, CameraRollAction, LocationAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage, FileMessage,
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent,
    MemberJoinedEvent, MemberLeftEvent,
    FlexSendMessage, BubbleContainer, ImageComponent, BoxComponent,
    TextComponent, IconComponent, ButtonComponent,
    SeparatorComponent, QuickReply, QuickReplyButton,
    ImageSendMessage)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1)

# get channel_secret and channel_access_token from your environment variable
channel_secret = '3baf8383f4e3c2aa2629eaa8d6636598'
channel_access_token = '7HEhz3rg3V1qtNvwq/x6/bIeOxajDm5pJe0jK1DSk301DSXGE0TKRGmRIA48+6jtw+JHoQpQ9NQF3mi6++ivxC/u/VOaHA2in2DUUJ2BxSS1qKS0n5C8TU7u8ErEeyEqFjhoYK+vPAt3y1zZIbKwkAdB04t89/1O/w1cDnyilFU='
if channel_secret is None or channel_access_token is None:
    print('Specify LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN as environment variables.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')


# function for create tmp dir for download content
def make_static_tmp_dir():
    try:
        os.makedirs(static_tmp_path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(static_tmp_path):
            pass
        else:
            raise


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except LineBotApiError as e:
        print("Got exception from LINE Messaging API: %s\n" % e.message)
        for m in e.error.details:
            print("  %s: %s" % (m.property, m.message))
        print("\n")
    except InvalidSignatureError:
        abort(400)

    return 'OK'

print("Loading Model...")
with open("./model/savedModel.pickle", "rb") as file:
    loaded_model = pickle.load(file)
print("*Model Loaded*")


prompt_dict = {}
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):

    text = event.message.text
    user_id = event.source.user_id

    def isEnglish(s):
        return s.isascii()
    def getDate():
        now = datetime.now()
        str_time = now.strftime("%dl%ml%y_%Hl%Ml%S")
        return str_time

    def generateIMG(prompt,model):  ## ฟังก์ชั่น Genetate ภาพ โยน str prompt , Model
        
        str_time=getDate();
        
        try:
            image = model(prompt,width=512, height=512,num_inference_steps=150).images[0]  
        except RuntimeError as e:
            return "Error: " + str(e)

        path = r'./static/output'
        if(not os.path.isdir(path)):
            os.mkdir(path)


        filename = prompt.replace(" ", "_")
        if(filename.isalnum()):
            filename = str_time+"-"+filename
        else:
            nfilename = ''
            for c in filename:
                if(c.isalnum() or c=='_'):
                    nfilename = nfilename+c
            filename = str_time+"-"+nfilename
        image.save(path+r"/"+filename+".png")
        
        return(filename+".png")
    
    

    if( text.startswith('GEN:') or text.startswith('ขอภาพ:') or text.startswith('gen:') ):  # Woking Here

        
        prompt = text.split(':')[1]
        if isEnglish(prompt):
            prompt_dict[user_id] = prompt
            # Send the "Generating..." response using the original reply token
            line_bot_api.reply_message(
                event.reply_token, [
                TextSendMessage(text='Generating...')
                ]
            )
            print("Incoming Prompt...")


            url_or_error = generateIMG(prompt, loaded_model)
            if url_or_error.startswith("Error:"):
                error_message = url_or_error
                line_bot_api.reply_message(
                    event.reply_token, [
                        TextSendMessage(text=error_message)
                    ]
            )
            else:
                url = request.url_root + '/static/output/' + url_or_error
                print(url)
                # Send the generated image using a new reply token
                new_token = event.reply_token
                line_bot_api.push_message(
                    event.source.user_id, [
                    TextSendMessage(text='Prompt: '+prompt),
                    ImageSendMessage(url, url)
                    ]
                )
        else:
            line_bot_api.reply_message(
                event.reply_token, [
                TextSendMessage(text='Please use only English character for the prompt')
                ]
            )

    elif( text.startswith('ขอภาพ\"') or text.startswith('GEN\"') or text.startswith('gen\"') ):  # Woking Here

        
        prompt = text.split('\"')[1]
        if isEnglish(prompt):
            prompt_dict[user_id] = prompt
            # Send the "Generating..." response using the original reply token
            line_bot_api.reply_message(
                event.reply_token, [
                TextSendMessage(text='Generating...')
                ]
            )
            print("Incoming Prompt...")

            url_or_error = generateIMG(prompt, loaded_model)
            if url_or_error.startswith("Error:"):
                error_message = url_or_error
                line_bot_api.reply_message(
                    event.reply_token, [
                        TextSendMessage(text=error_message)
                    ]
            )
            else:
                url = request.url_root + '/static/output/' + url_or_error
                print(url)
                # Send the generated image using a new reply token
                new_token = event.reply_token
                line_bot_api.push_message(
                    event.source.user_id, [
                    TextSendMessage(text='Prompt: '+prompt),
                    ImageSendMessage(url, url)
                    ]
                )
            
        else:
            line_bot_api.reply_message(
                event.reply_token, [
                TextSendMessage(text='Please use only English character for the prompt')
                ]
            )
    elif ( text.lower() == 'Repeat' or text == 'ขอภาพอีก' or text == 'อีกครั้ง' or text == 'r'):
        if user_id in prompt_dict:
            prompt = prompt_dict[user_id]
            line_bot_api.reply_message(
                event.reply_token, [
                TextSendMessage(text='Generating...')
                ]
            )
            print("Incoming Prompt... (Repeat)")

            

            url = request.url_root + '/static/output/' + generateIMG(prompt,loaded_model)
            print(url)

            # Send the generated image using a new reply token
            new_token = event.reply_token
            line_bot_api.push_message(
                event.source.user_id, [
                TextSendMessage(text='Prompt: '+prompt),
                ImageSendMessage(url, url)
                ]
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="Sorry, you haven't entered a prompt yet.")
            )
    elif (text.find('ขอบคุณ') != -1) or (text.find('thank') != -1) or (text.find('Thank') != -1) or (text.find('thx') != -1):
        line_bot_api.reply_message(
        event.reply_token,
        StickerSendMessage(
            package_id=11537,
            sticker_id=52002735)
    )
    
    elif (text.lower() == "test"):
        line_bot_api.reply_message(
                event.reply_token, [
                TextSendMessage(text='TEST')
                ]
            )
        
    elif (text == "?"):
        line_bot_api.reply_message(
                event.reply_token, [
                TextSendMessage(text='วิธีการใช้งาน\nในการ generate ภาพมีรูปแบบดังนี้\n- ขอภาพ"(คำอธิบาย)" \n- gen:(คำอธิบาย)\n- ขอภาพอีก\n- Repeat'),
                
                ]
            )
        
    else :
        emojis = [
            {
                "index": 41,
                "productId": "5ac1bfd5040ab15980c9b435",
                "emojiId": "004"
            },
        ]
        text_message = TextSendMessage(text='Is that a typo?  I don\'t know what it is $' , emojis=emojis)

        line_bot_api.reply_message(
                event.reply_token, [
                    text_message 
                ]
            )

   
@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        LocationSendMessage(
            title='Location', address=event.message.address,
            latitude=event.message.latitude, longitude=event.message.longitude
        )
    )


@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    
    print(event.message.package_id)
    print(event.message.sticker_id)
    
    line_bot_api.reply_message(
        event.reply_token,
        StickerSendMessage(
            package_id=event.message.package_id,
            sticker_id=event.message.sticker_id)
    )
    
    

@handler.add(MessageEvent, message=FileMessage)
def handle_file_message(event):
    message_content = line_bot_api.get_message_content(event.message.id)
    with tempfile.NamedTemporaryFile(dir=static_tmp_path, prefix='file-', delete=False) as tf:
        for chunk in message_content.iter_content():
            tf.write(chunk)
        tempfile_path = tf.name

    dist_path = tempfile_path + '-' + event.message.file_name
    dist_name = os.path.basename(dist_path)
    os.rename(tempfile_path, dist_path)

    line_bot_api.reply_message(
        event.reply_token, [
            TextSendMessage(text='Save file.'),
            TextSendMessage(text=request.host_url + os.path.join('static', 'tmp', dist_name))
        ])


@handler.add(FollowEvent)
def handle_follow(event):
    app.logger.info("Got Follow event:" + event.source.user_id)
    line_bot_api.reply_message(
        event.reply_token, TextSendMessage(text='Got follow event'))


@handler.add(UnfollowEvent)
def handle_unfollow(event):
    app.logger.info("Got Unfollow event:" + event.source.user_id)


@handler.add(JoinEvent)
def handle_join(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='Joined this ' + event.source.type))


@handler.add(LeaveEvent)
def handle_leave():
    app.logger.info("Got leave event")


@handler.add(PostbackEvent)
def handle_postback(event):
    if event.postback.data == 'ping':
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text='pong'))
    elif event.postback.data == 'datetime_postback':
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text=event.postback.params['datetime']))
    elif event.postback.data == 'date_postback':
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text=event.postback.params['date']))


@handler.add(BeaconEvent)
def handle_beacon(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text='Got beacon event. hwid={}, device_message(hex string)={}'.format(
                event.beacon.hwid, event.beacon.dm)))


@handler.add(MemberJoinedEvent)
def handle_member_joined(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text='Got memberJoined event. event={}'.format(
                event)))


@handler.add(MemberLeftEvent)
def handle_member_left(event):
    app.logger.info("Got memberLeft event")


@app.route('/static/<path:path>')
def send_static_content(path):
    return send_from_directory('static', path)


if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', type=int, default=8000, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    # create tmp dir for download content
    make_static_tmp_dir()

    app.run(debug=options.debug, port=options.port)
