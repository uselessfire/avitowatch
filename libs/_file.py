#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2015 Anton Karasev
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os


def __file(filename, text=None, ini=False):
    if text is None:
        if os.path.exists(filename):
            fp = open(filename, 'r')
            text = fp.read()
            fp.close()
            return text.decode('utf8')
        else:
            return _file(filename, str())
    else:
        if ini:
            if os.path.exists(filename):
                return _file(filename)
            else:
                return _file(filename, text)
        else:
            filename, text = unicode(filename), unicode(text)
            folder = os.path.dirname(filename)
            if folder and not os.path.exists(folder):
                os.makedirs(folder)
            with open(filename, 'w') as fp:
                fp.write(text)
            return text
