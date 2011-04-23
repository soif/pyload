# -*- coding: utf-8 -*-
from __future__ import with_statement

import re

from os import remove

from module.plugins.Hoster import Hoster
from module.plugins.ReCaptcha import ReCaptcha

from module.network.RequestFactory import getURL

def getInfo(urls):
    result = []
    
    for url in urls:
        
        # Get html
        html = getURL(url)
        if re.search(r'<h1>Error - File not available</h1>', html):
            result.append((url, 0, 1, url))
        
        attribs = re.search('<h1>Downloading (.+?) - (\d+) (..)yte</h1>', html)
        # Name
        name = attribs.group(1)
        
        # Size
        units = float(attribs.group(2))
        pow = {'KB' : 1, 'MB' : 2, 'GB' : 3}[attribs.group(3)] 
        size = int(units*1024**pow)
    
        # Return info
        result.append((name, size, 2, url))
        
    yield result

class BitshareCom(Hoster):
    __name__ = "BitshareCom"
    __type__ = "hoster"
    __pattern__ = r"http://(www\.)?bitshare\.com/(files/[a-zA-Z0-9]+|\?f=[a-zA-Z0-9]+)"
    __version__ = "0.1"
    __description__ = """Bitshare.Com File Download Hoster"""
    __author_name__ = ("paul", "king")
        
    def setup(self):
        self.multiDL = False

    def process(self, pyfile):
    
        self.pyfile = pyfile
    
        if re.search(r"bitshare\.com/\?f=",self.pyfile.url):
            self.file_id = re.search(r"bitshare\.com/\?f=([a-zA-Z0-9]+)?", self.pyfile.url).group(1)
        else:
            self.file_id = re.search(r"bitshare\.com/files/([a-zA-Z0-9]+)?", self.pyfile.url).group(1)

        self.log.debug("%s: file_id is %s" % (self.__name__,self.file_id))
        self.pyfile.url = r"http://bitshare.com/?f=" + self.file_id

        self.html = self.load(self.pyfile.url, ref=False, utf8=True)

        if re.search(r'<h1>Error - File not available</h1>', self.html) is not None:
            self.offline()
           
        self.pyfile.name = re.search(r'<h1>Downloading (.+?) - (\d+) (..)yte</h1>', self.html).group(1)

        self.ajaxid = re.search("var ajaxdl = \"(.*?)\";",self.html).group(1)
        
        self.log.debug("%s: AjaxId %s" % (self.__name__,self.ajaxid))

        self.handleFree()
    
    def handleFree(self):

        action = self.load("http://bitshare.com/files-ajax/" + self.file_id + "/request.html",
                            post={"request" : "generateID", "ajaxid" : self.ajaxid})
        self.log.debug("%s: result of generateID %s" % (self.__name__,action))
        parts = action.split(":")
    
        if parts[0] == "ERROR":
            self.fail(parts[1])
        
        filetype = parts[0]
        wait = int(parts[1])
        captcha = int(parts[2])

        if wait > 0:
            self.log.info("%s: Waiting %d seconds." % (self.__name__, wait))
            self.setWait(wait, True)
            self.wait()
            
        if captcha == 1:
            id = re.search(r"http://api\.recaptcha\.net/challenge\?k=(.*?) ", self.html).group(1)
            self.log.debug("%s: ReCaptcha key %s" % (self.__name__, id))
            for i in range(3):   # Try upto 3 times
                recaptcha = ReCaptcha(self)
                challenge, code = recaptcha.challenge(id)
                action = self.load("http://bitshare.com/files-ajax/" + self.file_id + "/request.html",
                                post={"request" : "validateCaptcha", "ajaxid" : self.ajaxid, "recaptcha_challenge_field" : challenge, "recaptcha_response_field" : code})
                parts = action.split(":")
                if parts[0] != "SUCCESS":
                    self.invalidCaptcha()
                else:
                    break

        action = self.load("http://bitshare.com/files-ajax/" + self.file_id + "/request.html",
                    post={"request" : "getDownloadURL", "ajaxid" : self.ajaxid})

        parts = action.split("#")
    
        if parts[0] == "ERROR":
            self.fail(parts[1])

        # this may either download our file or forward us to an error page
        self.log.debug("%s: download url %s" % (self.__name__, parts[1]))
        dl = self.download(parts[1])