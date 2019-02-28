import json
import os
from hashlib import md5
from multiprocessing import Pool

import pymongo
import re
from urllib.parse import urlencode
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from Config import *

client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]

headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.75 Safari/537.36',
    'x-requested-with': 'XMLHttpRequest',
}

def get_page_index(offset, keyword):
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': '20',
        'cur_tab': '3',
        'from': 'gallery',
    }
    url = 'https://www.toutiao.com/search_content/?' + urlencode(data)
    response = requests.get(url)
    try:
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('搜索页出错!')
        return None

def parse_page_index(html):
    data = json.loads(html)
    if 'data' in data.keys():
        for item in data.get('data'):
            yield item.get('article_url')

def get_page_detail(url):
    response = requests.get(url, headers=headers)
    try:
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('详情页出错!', url)
        return None

def parse_page_detail(html, url):
    try:
        soup = BeautifulSoup(html, 'lxml')
        title = soup.select('title')[0].get_text()
        print(title)
        images_pattern = re.compile('gallery:.*?"(.*?)"\),', re.S)
        result = re.search(images_pattern, html)
        if result:
            data = json.loads(result.group(1).replace('\\', ''))
            if 'sub_images' in data.keys():
                sub_images = data.get('sub_images')
                images = [item.get('url') for item in sub_images]
                for image in images: download_image(image)
                return {
                    'title': title,
                    'url': url,
                    'images': images
                }
    except:
        print('error')

def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        return True
    return False

def download_image(url):
    print('正在下载：', url)
    response = requests.get(url)
    try:
        if response.status_code == 200:
            save_image(response.content)
        return None
    except RequestException:
        print('请求图片出错!', url)
        return None

def save_image(content):
    file_path = '{0}/{1}/{2}.{3}'.format(os.getcwd(), 'img', md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()

def main(offset):
    html = get_page_index(offset, KEYWORD)
    for url in parse_page_index(html):
        html = get_page_detail(url)
        if html:
            result = parse_page_detail(html, url)
            if result: save_to_mongo(result)

if __name__ == '__main__':
    groups = [x * 20 for x in range(PAGEBEGIN, PAGEEND + 1)]
    pool = Pool()
    pool.map(main, groups)