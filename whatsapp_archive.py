#!/usr/bin/python3

"""Reads a WhatsApp conversation export file and writes a HTML file."""

import argparse
import sys
from string import Template
import hashlib
import datetime
import dateutil.parser
from pprint import pprint
import html
import itertools
import jinja2
import logging
import os.path
import re

# Format of the standard WhatsApp export line. This is likely to change in the
# future and so this application will need to be updated.
DATE_RE = '(?P<date>[\d/-]+)'
LRM = r'\u200e'
LRM_OPT = LRM + '?'
TIME_RE = '(?P<time>[\d:]+( [AP]M)?)'
DATETIME_RE = '\[?' + DATE_RE + ',? ' + TIME_RE + '\]?'
SEPARATOR_RE = '( - |: | )'
NAME_RE = '(?P<name>[^:]+)'
WHATSAPP_RE = (
    LRM_OPT
    + DATETIME_RE 
    + SEPARATOR_RE 
    +NAME_RE 
    + ': ' 
    + LRM_OPT 
    + '(?P<body>.*$)')

FIRSTLINE_RE = (DATETIME_RE +
               SEPARATOR_RE +
               '(?P<body>.*$)')


class Error(Exception):
    """Something bad happened."""


colorLUT = {}
    
def getColor(userName):
    """produce a css string for use as a color: value """
    if userName in colorLUT:
        return colorLUT[userName];
    
    hash = hashlib.md5();
    hash.update(userName.encode('utf-8'));
    hue = int.from_bytes(hash.digest(),byteorder='big',signed=False) % 360
    colorStr =  Template("hsl($hue,76%, 36%)").substitute(hue=hue)
    colorLUT[userName] = colorStr;
    return colorStr;
   
def ParseLine(line):
    """Parses a single line of WhatsApp export file."""
    if(0==  len(line)):
        return None;
    m = re.match(WHATSAPP_RE, line, re.DOTALL)
    if m:
        d = dateutil.parser.parse("%s %s" % (m.group('date'),
            m.group('time')), dayfirst=True)
        return {
	    'date': d,
	    'user': m.group('name'),
	    'color': getColor(m.group('name')),
	    'body': massageBody(m.group('body'))
        }
    # Maybe it's the first line which doesn't contain a person's name.
    m = re.match(FIRSTLINE_RE, line, re.DOTALL)
    if m:
        d = dateutil.parser.parse("%s %s" % (m.group('date'),
            m.group('time')), dayfirst=True)
        return {
	    'date':d, 
	    'user': "nobody", 
            'body': massageBody(m.group('body'))
        }
    m = re.match(
        DATETIME_RE + SEPARATOR_RE + NAME_RE
        +r': '
        +r'(?P<body>.*)', line,  re.DOTALL)
    logging.warn ("parse fail for line: ")
    logging.warn (line.encode("utf-8"));
    return None


ATTACHMENT_IMG_RE = r'&lt;attached: (?P<filename>.+\.(jpe?g|png|gif|webp))&gt;'
ATTACHMENT_MOV_RE = r'&lt;attached: (?P<filename>.+\.(mp4|mov|3gp))&gt;'
ATTACHMENT_AUDIO_RE = r'&lt;attached: (?P<filename>.+\.(opus))&gt;'
def massageBody(body):

    body = re.sub(r'&',"&amp;", body)
    body = re.sub(r'<',"&lt;", body)
    body = re.sub(r'>',"&gt;", body)
    body = re.sub(r'(?P<link>https?://.[^ \n<]+)', r'<a href="\g<link>">\g<link></a>', body)
    if  re.search(ATTACHMENT_IMG_RE, body, re.IGNORECASE):
        body =  re.sub(ATTACHMENT_IMG_RE, r'<a href="\g<filename>"><img src="\g<filename>"></a>', body, flags=re.IGNORECASE)
    elif  re.search(ATTACHMENT_MOV_RE, body, re.IGNORECASE):
        body =  re.sub(ATTACHMENT_MOV_RE, r'<a href="\g<filename>"><div class="container"><video src="\g<filename>"></video><div class="centered">PLAY</div></div></a>', body, flags=re.IGNORECASE)
    elif  re.search(ATTACHMENT_AUDIO_RE, body, re.IGNORECASE):
        body =  re.sub(ATTACHMENT_AUDIO_RE, r'<a href="\g<filename>"><audio controls><source src="\g<filename>" /></audio></a>', body, flags=re.IGNORECASE)
    fixed = re.sub(r'\n','<br>',body)
    return fixed
    
def IdentifyMessages(lines):
    """Input text is split by \rs.
    """
    messages = []
    msg_date = None
    msg_user = None
    msg_body = None
    for line in lines:
        messages.append( ParseLine(line))
    return messages


def TemplateData(messages, input_filename):
    """Create a struct suitable for procesing in a template.
    Returns:
        A dictionary of values.
    """
    by_user = []
    file_basename = os.path.basename(input_filename)
    # for user, msgs_of_user in itertools.groupby(messages, lambda x: x[1]):
    #     by_user.append((user, list(msgs_of_user)))
    return dict(messages=messages,
                input_basename=file_basename,
                input_full_path=input_filename)


def FormatHTML(data):
    tmpl = """<!DOCTYPE html>
    <html>
    <head>
        <title>WhatsApp archive {{ input_basename }}</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
.container {
    max-width :300px;
    position: relative;
    text-align: center;
    color: white;
}
.centered {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: large;
}
video{
    width: 100%;
    
}
img {
    max-width: 300px;
}
body {
    font-family: Segoe UI,Helvetica Neue,Helvetica,Lucida Grande,Arial,Ubuntu,Cantarell,Fira Sans,sans-serif;
    
    font-size: 10px;
    overflow:hidden;
    height: 100%;
    width: 100%;
    margin:0;
}
ol.message-list {
    background-color:#e5ddd5;
    list-style-type: none;
    list-style-position: inside;
    margin: 0;
    padding: 0;
}
.message-list li{
    margin:2px 5px;
    max-width: 65%;
}
.message-list .message{
    padding: 6px 7px 8px 9px;
    
    background-color:white;
    border-radius:7.5px;
    box-shadow:0 1px 0.5px rgba(0,0,0,.13);
    
}
.body {
    margin-left: 1em;
    font-size: 14.2px;
            }
span.username {
    color: #00bfa5;
    font-size: 12.8px;
    font-weight: 700;
    line-height: 22px;
}
.date-container-1{
    float:right;
    margin:-10px 0 -5px 4px;
}   
.date-container-2{
    color: rgba(0,0,0,.45);
    font-size: 11px;
    height: 15px;
    line-height: 15px;
    white-space:nowrap;
}
.date {
    display:inline-block;
}

.main{
    display:flex;
    flex-direction: column;
    height: calc(100vh - 38px);
    background-color: #e5ddd5;
    margin-top:19px;
}
header{
    flex: 0 0 59px;
    display:flex;
    order: 1;
    height: 59px;
    background-color: #ededed;
    padding: 10px 16px;
    width: 100%;
    align-items:center;
    position: relative;
    z-index:1000;
}

.message-list-container{
    flex: 1 1 0;
    order : 2 ;
    position: relative;
    z-index: 1;
    overflow:auto;
}

header img.group-image{
    width: 64px;
}


        </style>
    </head>
    <body>
<div class="main"> 
   <header>
	<a href="group-image.jpeg"><img  class='group-image' src="group-image.jpeg"></a>
        <h1>{{ input_basename }}</h1>

   </header>
   <div class="message-list-container">
        <ol class="message-list">
        {% for message in messages %}
            <li >
    <div class='message'>
              <span class="username" style="color: {{message.color}};">{{ message.user }}</span>
              <div class="body">
                  {{ message.body }}
              </div>
         <div class="date-container-1">
           <div class="date-container-2">
              <div class="date" data-fulldate="{{ message.date }}">
                 {{ message.date }}
              </div>
            </div>
          </div>
      </div>
            </li>
        {% endfor %}
        </ol>
    </div>
</div>
    </body>
    </html>
    """
    return jinja2.Environment().from_string(tmpl).render(**data)


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='Produce a browsable history '
            'of a WhatsApp conversation')
    parser.add_argument('-i', dest='input_file', required=True)
    parser.add_argument('-o', dest='output_file', required=True)
    args = parser.parse_args()
    with open(args.input_file, 'rb') as fd:
        body = fd.read()
        lines = [ str.decode('utf-8-sig')  for str in body.split( b'\r\n')]
        messages = IdentifyMessages(lines)
    template_data = TemplateData(messages, args.input_file)
    HTML = FormatHTML(template_data)
    with open(args.output_file, 'w', encoding='utf-8') as fd:
        fd.write(HTML)


if __name__ == '__main__':
    main()
