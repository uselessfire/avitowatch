#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# version: 0.10 Beta Public
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


import sys
import os
import urllib
import time
import datetime
import smtplib
import threading
import signal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from time import sleep

internet_lock = threading.Lock()

core = os.path.abspath(__file__)
coreDir = os.path.split(core)[0]

sys.path.insert(1, coreDir + '/libs')
import bs4
from __file import __file

reload(sys).setdefaultencoding('utf8')


class Item(object):
    def __init__(self, config, item):
        self.config = config
        # import pdb; pdb.set_trace()
        self.item_id = int(item['id'][1:])
        price = item.find('div', {'class': 'about'}).get_text().replace(' ', '').replace(u'\xa0', '').strip()
        if price:
            self.price = int(price[:-4])
        else:
            self.price = None
        main_link = item.find('h3', {'class': 'title'}).findChild()
        self.name = main_link.get_text(strip=True)
        temp = item.find('img', {'class': 'photo-count-show'})
        self.mainImageUrl = (urllib.basejoin(self.config['site'], temp['src']) if temp else None)
        self.link = urllib.basejoin(self.config['site'], main_link['href'])
        self.date = item.find('div', {'class': 'date c-2'}).get_text(strip=True)

        self.old_price = int()
        self.image_urls = list()
        self.images_html, self.address, self.city, self.seller_name, self.seller_type, self.description \
            = (unicode() for _ in xrange(0, 6))

    __int__ = lambda self: self.item_id
    __str__ = lambda self: self.name

    def grep_advanced(self):
        try:
            bs_item_page = bs4.BeautifulSoup(urllib.urlopen(self.link).read())
        except IOError:
            return False
        else:
            self.image_urls = list()
            only_one = bs_item_page.find('td', {'class': 'only-one'})
            if only_one:  # если фото всего одно
                self.image_urls.append(urllib.basejoin(self.config['site'], only_one.find('img')['src']))
                # добавляем только его
            else:  # если несколько
                for image in bs_item_page.findAll('div', {'class': 'gallery-item'}):  # добавляем все
                    self.image_urls.append(urllib.basejoin(self.config['site'], image.findChild()['href']))
            self.description = chr(10).join(bs_item_page.find('div', {'itemprop': 'description'}).strings).strip()
            self.seller_name = bs_item_page.find('strong', {'itemprop': 'name'}).get_text(strip=True)
            temp = bs_item_page.find('span', {'class': 'c-2'})
            if temp:
                self.seller_type = temp.get_text(strip=True).replace('(', '').replace(')', '')
            else:
                self.seller_type = u'физ. лицо'
            self.city = bs_item_page.find('span', {'itemprop': 'name'}).extract().get_text(strip=True)  # read and del
            self.address = bs_item_page.find('span', {'id': 'toggle_map'}).get_text()[1:].strip()
            return True

#    def download_images(self):
#        self.image_files = list()
#        for url in self.image_urls:
#            self.image_files.append(urllib.urlretrieve(url)[0])
#        return self.image_files
#
#    def delete_images(self):
#        for image in self.image_files:
#            os.remove(image)
#            del self.image_files[0]

    def send_or_not(self):
        if self.config['min_price'] <= self.price <= self.config['max_price'] and\
                (not filter(lambda exclusion: ((exclusion.lower() in self.description.lower()) or
                                               (exclusion in self.name)), self.config['exclusions'])):
            return True
        else:
            return False


def grep_items(config, url=None, page=1):
    items = list()
    if not url:
        url = config['main_url']
    try:
        internet_lock.acquire()  # авито не любит одновременные запросы
        sleep(1)
        html = urllib.urlopen(url).read()
        internet_lock.release()
        if not html:
            raise IOError
    except IOError:
        print 'error while open url %s' % url
    else:
        bs = bs4.BeautifulSoup(html)
        if bs.find('input', {'id': 'search'})['value'].lower() == config['search'].lower():
            # авито упрощает поисковый запрос, если ничего не найдено
            bs_items = bs.findAll('div', {'class': 'item'})
            for item in bs_items:
                items.append(Item(config, item))
            next_page = bs.find('a', {'class': 'pagination__page'}, text=u'\n Следующая страница →\n ')
            if next_page:
                items += grep_items(config, urllib.basejoin(config['site'], next_page['href']), page + 1)
    if page == 1:
        config['last_len'] = len(items)
        config['last_check'] = datetime.datetime.now()
        print_status()
    return items


class Email(object):
    def __init__(self, config):
        self.smtp, self.msg = None, None
        self.config = config

    def grep_advanced(self, item):
        if item.grep_advanced():
            for url in item.image_urls:
                item.images_html += '<img src="%s">' % url
            self.create_msg(item)
            # self.attach_images(item.download_images())
            # item.delete_images()
            return True
        else:
            return False

    create_price_subject = lambda self, item: self.config['default_price_change_subject'] %\
        (item.name, item.old_price, item.price)
    create_price_body = lambda self, item: self.config['default_price_change_html'] %\
        (item.link, item.name, item.old_price, item.price, item.description.replace('\n', '<br>'), item.item_id,
         item.date, item.seller_name, item.seller_type, item.city, item.address, item.images_html)

    create_new_subject = lambda self, item: self.config['default_new_subject'] % (item.name, item.price)
    create_new_body = lambda self, item: self.config['default_new_html'] %\
        (item.link, item.name, item.price, item.description.replace('\n', '<br>'), item.item_id, item.date,
         item.seller_name, item.seller_type, item.city, item.address, item.images_html)

    def create_msg(self, item):
        self.msg = MIMEMultipart()
        if item.old_price:
            self.msg['Subject'] = self.create_price_subject(item)
            self.msg.attach(MIMEText(self.create_price_body(item), 'html', _charset='utf-8'))
        else:
            self.msg['Subject'] = self.create_new_subject(item)
            self.msg.attach(MIMEText(self.create_new_body(item), 'html', _charset='utf-8'))
        #            __file('test.html', self.create_new_body(item))

#    def attach_images(self, images):
#        # не используется (изображения теперь в виде ссылок в HTML-письме, а не в виде приложенных файлов)
#        for image in images:
#            fp = open(image, 'rb')
#            self.msg.attach(MIMEImage(fp.read()))
#            fp.close()

    def send(self):
        self.msg['From'] = self.config['me']
        self.msg['To'] = self.config['to']
        internet_lock.acquire()
        if self.config['ssl']:
            self.smtp = smtplib.SMTP_SSL(self.config['server'], self.config['port'])
        else:
            self.smtp = smtplib.SMTP(self.config['server'], self.config['port'])
        print u'\x1b[2K\r[%s %s: %s]' % (datetime.datetime.now().strftime("%H:%M:%S"), self.config['configfile'],
                                         self.smtp.login(self.config['login'], self.config['password'])[1])
        code = self.smtp.sendmail(self.config['me'], self.config['to'], self.msg.as_string())
        self.smtp.quit()
        internet_lock.release()
        return code


def check_new(config):
    idfile = '.%s.dict' % config['configfile']
    lastids = eval(__file(idfile, dict(), True))
    newids = dict()
    delta = list()
    newitems = grep_items(config)
    for item in newitems:
        newids[item.item_id] = item.price
        if lastids:
            if item.item_id in lastids:
                if item.price < lastids[item.item_id]:
                    item.old_price = lastids[item.item_id]
                    delta.append(item)
            else:
                delta.append(item)
    if newitems:
        __file(idfile, str(newids))
    return delta


def print_status():
    to_print = unicode()
    for config in configs:
        if config['last_len']:
            to_print += u'[%s %s: %i results]   ' % (config['last_check'].strftime("%H:%M:%S"), config['configfile'],
                                                     config['last_len'])
    to_print += u'\r'
    sys.stdout.write(to_print)
    sys.stdout.flush()


def start_watcher(config):

    url = urllib.basejoin(config['site'], config['region'] +
                          (('/' + config['category']) if config['category'] else str()) + '/?q=%s')

    config['query'] = urllib.quote_plus(config['search'])
    config['main_url'] = url % config['query']
    while True:
        for item in check_new(config):
            if item.send_or_not():
                email = Email(config)
                if email.grep_advanced(item):
                    email.send()
                    print u'\x1b[2K\r[%s %s: Email sent with %i photos: %s ]' %\
                          (datetime.datetime.now().strftime("%H:%M:%S"),
                           config['configfile'],
                           len(item.image_urls),
                           item.link)

        time.sleep(config['timer'])


def main():
    global configs
    configs = list()
    for configfile in sys.argv[1:]:
        configs.append(dict())
        configs[-1]['configfile'] = configfile
        configs[-1]['last_len'] = None
        configs[-1]['last_check'] = None
        execfile(configfile, configs[-1])
        configs[-1]['thread'] = threading.Thread(None, start_watcher, configfile, (configs[-1],))
        configs[-1]['thread'].setDaemon(True)
        configs[-1]['thread'].start()
    signal.signal(signal.SIGINT, lambda _, __: sys.exit())
    signal.pause()
    return 0

if __name__ == '__main__':
    main()
