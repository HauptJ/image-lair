#!/usr/bin/env python
#
#    Copyright (C) 2008 Sylvain
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import wsgiref.handlers
import logging, os, re
import random, string, cgi
import datetime
import config

from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.api import images
from google.appengine.api import memcache
from google.appengine.api import mail
from google.appengine.api import urlfetch

_DEBUG = False

class Image(db.Model):
    name = db.TextProperty()
    is_url = db.BooleanProperty(indexed=False)
    type = db.StringProperty(indexed=False)
    extension = db.StringProperty(indexed=False)
    length = db.IntegerProperty(indexed=False)
    label = db.StringProperty(indexed=False)
    owner = db.UserProperty()
    date = db.DateTimeProperty(auto_now_add=True)
    original = db.BlobProperty()
    large = db.BlobProperty()
    medium = db.BlobProperty()
    small = db.BlobProperty()
    thumb_extension = db.StringProperty(indexed=False)
    thumb_type = db.StringProperty(indexed=False)
    del_key = db.StringProperty(indexed=False)

class Account(db.Model):
    user = db.UserProperty()
    
class BaseRequestHandler(webapp.RequestHandler):
    def generate(self, template_name, template_values={}):
        
        sign_url, sign_label, user_name, user_is_admin = get_user_info()
        host = self.request.host_url
        
        if not self.is_authorized():
            return self.redirect(sign_url)
                        
        values = {'user_name': user_name,
                  'user_is_admin': user_is_admin, 
                  'sign': sign_label,
                  'sign_url': sign_url,
                  'host': host,
                  'setting': config.is_private,
                  'size': config.image_size}
        
        values.update(template_values)
        directory = os.path.dirname(__file__)
        path = os.path.join(directory, os.path.join('templates', template_name))
        html = template.render(path, values, debug=_DEBUG)
        self.response.out.write(html)

    def is_authorized(self):
        if config.is_private and not users.is_current_user_admin():
            user = users.get_current_user()
            if not user or not is_user_account_exist(user):
                return False
        return True

class MainPage(BaseRequestHandler):
    def get(self):
        
        method = self.request.get('method','file')
        if method == 'file':
            template = 'upload_file.html'
        else:
            template = 'url_file.html'
        
        template_values = {}
        self.generate(template, template_values)
    
    def post(self):
        
        error = ''
        img = None
        allow_del = False
        user = users.get_current_user()
        file_name = ''
        is_url = False
        
        if 'url' in self.request.POST:
            url = self.request.get('url')
            try:
                if url:
                    result = urlfetch.fetch(url)
                    if result.status_code == 200:
                        image_length = int(result.headers['content-length'])
                        if image_length > config.max_size:
                            error = 'File is too large'
                        else:
                            file_data = result.content
                            file_content_type = result.headers['content-type']
                            logging.info(url)
                            file_name = url
                            is_url = True
            except Exception, e:
                logging.exception(e)
                error = e.message
       
        if ('file' in self.request.POST and 
           isinstance(self.request.POST.get('file', None),cgi.FieldStorage) and
           self.request.POST.get('file', None).filename):
                        
            file_data = self.request.POST.get('file').file.read()
            image_length = len(file_data)
            
            if image_length > config.max_size:
                error = 'File is too large'
            else:
                file_content_type = self.request.POST.get('file').type
                file_name = self.request.POST.get('file').filename
                
            
        if file_name:
                label = self.request.POST.get('label')
                img_key = random_string(25)
                template = 'image_base.html'
                
                try:
                    ext_original, ext_thumbnail, o_encoding, o_content_type  = get_image_extension(file_content_type)
                    
                    img = Image(key_name=img_key)
                    img.name = db.Text(file_name) #to store long URL
                    img.is_url = is_url
                    img.original = db.Blob(file_data)
                    img.large = db.Blob(images.resize(file_data, width=config.image_size['large'][0], output_encoding=o_encoding))
                    img.medium = db.Blob(images.resize(file_data, width=config.image_size['medium'][0], output_encoding=o_encoding))
                    img.small = db.Blob(images.resize(file_data, width=config.image_size['small'][0], output_encoding=o_encoding))          
                    img.type = file_content_type
                    img.extension = ext_original
                    img.owner = user
                    img.label = label
                    img.length = image_length
                    img.thumb_extension = ext_thumbnail
                    img.thumb_type = o_content_type
                    img.del_key = random_string(10)
                    
                    #estimate the size before put()
                    l = len(img.large) + len(img.medium) + len(img.small) + image_length
                    if l > config.max_size * 995/1000:
                        raise Exception("NoPix object is too big,... upload another image... Sorry...")

                    img.put()
                    memcache.set(img_key,img)
                    logging.info('File name : %s' % file_name)
                    
                except Exception, e:
                    logging.exception(e)
                    error = e.message
        else:
            template = 'upload_file.html'
        
        template_values = {'img': img,
                           'error': error,
                           'allow_del': True}
        self.generate(template, template_values)

class ImagePage(BaseRequestHandler):
    def get(self, key):
        
        template = 'upload_file.html'
        allow_del = False
        
        img = get_image(key)
        if img:
            if self.request.get('del') == img.del_key:
                    template = 'upload_file.html'
                    memcache.delete(key)
                    img.delete()
                    img = None
            else:
                user = users.get_current_user()
                if user and (user == img.owner or users.is_current_user_admin()):
                    template = 'image_base.html'
                    allow_del = True
                else:
                    template = 'image_base.html'
                    #template = 'image_only.html' #NO LINKS
                    allow_del = False
        
        template_values = {'img': img,
                           'allow_del': allow_del}
        self.generate(template, template_values)

class GetImage(BaseRequestHandler):
    def get(self, size, key):
        try:
            img = get_image(key)
            if not img:
                return                
            
            content_type = img.thumb_type
            if size == 'o':
                data = img.original
                content_type = img.type
            elif size == 'l':
                data = img.large
            elif size == 's':
                data = img.small
            else: # medium
                data = img.medium
            
            expires=datetime.datetime.now() + datetime.timedelta(days=365)
            
            self.response.headers['Expires'] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
            self.response.headers['Cache-Control']='public, max-age=31536000'
            self.response.headers['Content-Type'] = str(content_type)
            self.response.out.write(data)
            
        except Exception, e:
            logging.exception(e)

class History(BaseRequestHandler):
    def get(self):
        
        if not users.get_current_user():
            self.redirect('/')
            return
        
        if self.request.get('action') == 'Del selected':
            keys = self.request.get('image', allow_multiple=True)
            to_delete = [db.Key.from_path('Image', k) for k in keys]
            db.delete(to_delete)
        
        label_size = sorted(config.image_size.keys(), reverse=True)    
        
        size = self.request.get('size','small')
        if size not in label_size:
            size = 'small'
        
        number = self.request.get('num','20')
        number = int(number) if number.isdigit() else 20
        
        img = Image.all()
        img.order('-date')
        
        if not users.is_current_user_admin():
            img.filter('owner = ', users.get_current_user())
        
        images = img.fetch(number)
        count = len(images)
        images = self.grouper(config.image_size[size][1], images)
                
        template_values = {'size': size[0], #l,m,s
                           'width': config.image_size[size][0], #150, 300,...
                           'conf': config.image_size,
                           'label_size': label_size,
                           'images': images,
                           'count': count}
        
        self.generate('history.html', template_values)
    
    def grouper(self, n, iterable, padvalue=None):
        from itertools import izip, chain, repeat
        "grouper(3, 'abcdefg', 'x') --> ('a','b','c'), ('d','e','f'), ('g','x','x')"
        return izip(*[chain(iterable, repeat(padvalue, n-1))]*n)
        
    post = get
        
class Settings(BaseRequestHandler):
    def post(self):
        if not users.is_current_user_admin():
            self.redirect('/')
            return
        
        message = ''
        action = self.request.get('action')
        
        if action == 'Add':
            user_email = self.request.get('newemail')
            if re.match('^[\w\.-]+@([\w-]+\.)+[\w-]{2,4}$', user_email):
                new_user = users.User(user_email)
                account = Account(user=new_user)
                account.put()
                if config.send_mail:
                    mail.send_mail(sender=users.get_current_user().email(), #it must be an admin
                                   to=user_email,
                                   subject=config.mail_subject,
                                   body=config.mail_body)
                    message = 'Mail sent'
            else:
                message = 'This is an invalid e-mail'
        elif action == 'Del':
            emails = self.request.POST.getall('email')
            for email in emails:
                if email:
                    db.delete(Account.get(email))
        
        accounts = Account.all()
        template_values = {'accounts': accounts,
                           'message': message}

        self.generate('settings.html', template_values)

    get = post

class Admin(BaseRequestHandler):
    def get(self):
        if not users.is_current_user_admin():
            self.redirect('/')
            return
        
        action = self.request.get('action')
        
        if action == 'view':
            key = self.request.get('key')
            if key:
                pass
            else:
                for im in Image.all():
                    self.response.out.write('Image : %s | %s | %s | %s | %s<br />\n' % (im.name, im.key().name(), im.length, im.type, im.owner))
        elif action == 'delall':
            for im in Image.all():
                self.response.out.write('Image deleted : %s | %s | %s | %s | %s<br />\n' % (im.name, im.key().name(), im.length, im.type, im.owner))
                im.delete()

def is_user_account_exist(current_user):
    accounts = Account.all()
    accounts.filter('user = ', current_user)
    return accounts.get()

def get_image(key):
    img = memcache.get(key)
    if img is not None:
       return img
    else:
        img = Image.get_by_key_name(key)
        memcache.add(key, img)
        return img

def get_user_info():
    user = users.get_current_user()
        
    if user:
        sign_url = users.create_logout_url('/')
        sign_label = 'Sign out'
        user_name = users.get_current_user().email()
        is_admin = users.is_current_user_admin()
    else:
        sign_url = users.create_login_url('/')
        sign_label = 'Sign in'
        user_name = ''
        is_admin = False

    return sign_url, sign_label, user_name, is_admin

def get_image_extension(type):
    enc = {'image/png':['.png','.png',images.PNG,'image/png'],
           'image/x-png':['.png','.png',images.PNG,'image/png'],
           'image/jpeg':['.jpg','.jpg',images.JPEG,'image/jpeg'],
           'image/pjpeg':['.jpg','.jpg',images.JPEG,'image/jpeg'],
           'image/x-jpeg':['.jpg','.jpg',images.JPEG,'image/jpeg'],
           'image/gif':['.gif','.png',images.PNG, 'image/png'],
           'image/x-gif':['.gif','.png',images.PNG, 'image/png'],
           'image/bmp':['.bmp','.jpg',images.JPEG, 'image/jpeg'],
           'image/x-bmp':['.bmp','.jpg',images.JPEG, 'image/jpeg'],
           'image/tiff':['.tif','.jpg',images.JPEG, 'image/jpeg'],
           'image/x-tiff':['.tif','.jpg',images.JPEG, 'image/jpeg'],
           'image/icon':['.ico','.png',images.PNG, 'image/png'],
           'image/x-icon':['.ico','.png',images.PNG, 'image/png']}
    
    try:
        enc_type = enc[type]
    except:
        raise Exception('This format %s is not supported' % type)
    
    return enc_type[0], enc_type[1], enc_type[2], enc_type[3]                  

def random_string(length=25):
    return ''.join([random.choice(string.ascii_letters + string.digits) for x in xrange(length)])

def main():
    application = webapp.WSGIApplication([('/', MainPage),
                                          ('/admin', Admin),
                                          ('/history', History),
                                          ('/settings', Settings),
                                          ('/(o|m|l|s)/(.*)\..*',GetImage),
                                          ('/(.*)', ImagePage)],
                                         debug=_DEBUG)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
