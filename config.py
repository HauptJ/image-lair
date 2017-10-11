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

#NoPix is private (True) and you need to create account (class Account)
#Only admin or authorized account could sign
#Add a new account in the "Settings" page
is_private = False

#Picture size - label : (size, column, max par page in history)
image_size = {'small': (150, 5, 100),
              'medium' : (300, 3, 50),
              'large' : (500, 2, 20)}

#Default max size for an image (1 MB = Google App Engine Quota)
max_size = 1000000

#If you set up your NoPix "private", you can automatically send a mail to that user
send_mail = True
mail_subject = "Welcome to NoPix"
mail_body = """
Hi,

Your NoPiX account has been approved.  You can now visit
http://nopix.appspot.com/ and sign in using your Google Account to
access new features.

Please let us know if you have any questions.

The NoPix Team
"""