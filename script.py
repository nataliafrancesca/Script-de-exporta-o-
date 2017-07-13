# -*- coding: utf-8 -*-
import json
import datetime
import csv
import time
import mysql.connector
from mysql.connector import errorcode

#Importa uma lista de ids presentes em um arquivo csv.
arquivoExemplo = open('lista.ID.csv')
leitorArquivo = csv.reader(arquivoExemplo)
pageId = []

for row in leitorArquivo:
    pageId.append(row[0])

try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request
#Criação da tabela em um banco de dados já pré-definido(arquvio config)

from config import config, access_token

cnx = mysql.connector.connect(**config)
cursor = cnx.cursor()

cursor.execute("DROP TABLE IF EXISTS posts")
cursor.execute('SET NAMES utf8mb4')
cursor.execute("SET CHARACTER SET utf8mb4")
cursor.execute("SET character_set_connection=utf8mb4")
cnx.commit()

# O "CHARACTER SET utf8mb4" serve para eviar o erro de encode, repassando a configuração de UTF-8 ao MySQL.
table_name = 'posts'
table = ("CREATE TABLE `posts` ("
         "  `cod` int(11) NOT NULL AUTO_INCREMENT,"
         "  `pageId` TEXT CHARACTER SET utf8mb4,"
         "  `status_id` TEXT CHARACTER SET utf8mb4," 
         "  `status_message` TEXT CHARACTER SET utf8mb4,"
         "  `link_name` TEXT CHARACTER SET utf8mb4,"
         "  `status_type` TEXT CHARACTER SET utf8mb4,"
         "  `status_link` TEXT CHARACTER SET utf8mb4,"
         "  `status_published` TEXT CHARACTER SET utf8mb4,"
         "  `num_reactions` int(11),"
         "  `num_comments` int(11),"
         "  `num_shares` int(11),"
         "  `num_likes` int(11),"
         "  `num_loves` int(11),"
         "  `num_wows` int(11),"
         "  `num_hahas` int(11),"
         "  `num_sads` int(11),"
         "  `num_angrys` int(11),"
         "  PRIMARY KEY (`cod`)"
         ") ENGINE=InnoDB")

cursor.execute(table)

def create_db_table():
    cursor.execute('SHOW DATABASES;')
    all_dbs = cursor.fetchall()
    if all_dbs.count((config['database'],)) == 0:
        print("Creating db")
        cursor.execute(
            "CREATE DATABASE {} DEFAULT CHARACTER SET 'utf8'".format(config['database']))

    cursor.execute('USE %s;' % config['database'])
    cursor.execute("SHOW TABLES;")
    all_tables = cursor.fetchall()
    if all_tables.count(('pages',)) == 0:
        print("creating table")
        cursor.execute(table)


add_message = ("INSERT INTO posts "
               "(pageId, status_id, status_message, link_name, \
               status_type, status_link, status_published, \
               num_reactions, num_comments, num_shares, num_likes, num_loves, num_wows, num_hahas, num_sads, num_angrys)"
               "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")


def insert_post(pageId, status_id, status_message, link_name, status_type, status_link,
                status_published, num_reactions, num_comments, num_shares, num_likes,
                num_loves, num_wows, num_hahas, num_sads, num_angrys):
      
    cursor.execute(add_message, (pageId, status_id, status_message, link_name, status_type, status_link,
                    status_published, num_reactions, num_comments, num_shares, num_likes, num_loves,
                    num_wows, num_hahas, num_sads, num_angrys))
    cnx.commit()

app_id = "226997921088693"
app_secret = "24a5f7ac0b1620b0b59145fba97d5125"
access_token = app_id + "|" + app_secret


def request_until_succeed(url):
    cont = 0
    req = Request(url)
    success = False
    while success is False:
        try:
            response = urlopen(req)
            if response.getcode() == 200:
                success = True
        except Exception as e:
            print(e)
            time.sleep(5)
            print("Error for URL {}: {}".format(url, datetime.datetime.now()))
            print("Retrying.")
                      
    return response.read().decode('utf-8') #Usei o .decode('utf-8') porque estava dando erro: "TypeError: the JSON object must be str, not 'bytes'"


# Needed to write tricky unicode correctly to csv
def unicode_decode(text):
    try:
        return text.encode('utf-8').decode()
    except UnicodeDecodeError:
        return text.encode('utf-8')


def getFacebookPageFeedUrl(base_url):

    # Construct the URL string; see http://stackoverflow.com/a/37239851 for
    # Reactions parameters
    fields = "&fields=message,link,created_time,type,name,id," + \
        "comments.limit(0).summary(true),shares,reactions" + \
        ".limit(0).summary(true)"

    return base_url + fields


def getReactionsForStatuses(base_url):
    reaction_types = ['like', 'love', 'wow', 'haha', 'sad', 'angry']
    reactions_dict = {}   # dict of {status_id: tuple<6>}

    for reaction_type in reaction_types:
        fields = "&fields=reactions.type({}).limit(0).summary(total_count)".format(
            reaction_type.upper())

        url = base_url + fields

        data = json.loads(request_until_succeed(url))['data']

        data_processed = set()  # set() removes rare duplicates in statuses
        for status in data:
            id = status['id']
            count = status['reactions']['summary']['total_count']
            data_processed.add((id, count))

        for id, count in data_processed:
            if id in reactions_dict:
                reactions_dict[id] = reactions_dict[id] + (count,)
            else:
                reactions_dict[id] = (count,)

    return reactions_dict


def processFacebookPageFeedStatus(status):

    # The status is now a Python dictionary, so for top-level items,
    # we can simply call the key.

    # Additionally, some items may not always exist,
    # so must check for existence first

    status_id = status['id']
    status_type = status['type']

    status_message = '' if 'message' not in status else \
        unicode_decode(status['message'])
    link_name = '' if 'name' not in status else \
        unicode_decode(status['name'])
    status_link = '' if 'link' not in status else \
        unicode_decode(status['link'])

    # Time needs special care since a) it's in UTC and
    # b) it's not easy to use in statistical programs.

    status_published = datetime.datetime.strptime(
        status['created_time'], '%Y-%m-%dT%H:%M:%S+0000')
    status_published = status_published + \
        datetime.timedelta(hours=-5)  # EST
    status_published = status_published.strftime(
        '%Y-%m-%d %H:%M:%S')  # best time format for spreadsheet programs

    # Nested items require chaining dictionary keys.

    num_reactions = 0 if 'reactions' not in status else \
        status['reactions']['summary']['total_count']
    num_comments = 0 if 'comments' not in status else \
        status['comments']['summary']['total_count']
    num_shares = 0 if 'shares' not in status else status['shares']['count']

    return (status_id, status_message.encode("utf-8"), link_name.encode("utf-8"), status_type.encode("utf-8"), status_link.encode("utf-8"),
            status_published, num_reactions, num_comments, num_shares)

def scrapeFacebookPageFeedStatus(page_id, access_token):
    has_next_page = True
    num_processed = 0
    scrape_starttime = datetime.datetime.now()
    after = ''
    base = "https://graph.facebook.com/v2.9"
    node = "/{}/posts".format(page_id)
    parameters = "/?limit={}&access_token={}".format(100, access_token)

    print("Scraping {} Facebook Page: {}\n".format(page_id, scrape_starttime))

    while has_next_page:
        after = '' if after is '' else "&after={}".format(after)
        base_url = base + node + parameters + after
        
        url = getFacebookPageFeedUrl(base_url)
        statuses = json.loads(request_until_succeed(url))
        reactions = getReactionsForStatuses(base_url)
       
        for status in statuses['data']:

            # Ensure it is a status with the expected metadata
            if 'reactions' in status:
                    status_data = processFacebookPageFeedStatus(status)
                    reactions_data = reactions[status_data[0]]
                    insert_post(pageId = pageId[aux], status_id = status_data[0], status_message = status_data[1], link_name = status_data[2],
                                status_type = status_data[3], status_link = status_data[4], status_published = status_data[5],
                                num_reactions = status_data[6], num_comments = status_data[7], num_shares = status_data[8],
                                num_likes = reactions_data[0], num_loves = reactions_data[1], num_wows = reactions_data[2],
                                num_hahas = reactions_data[3], num_sads = reactions_data[4], num_angrys = reactions_data[5])
            time.sleep(0.5)
            num_processed += 1
            print(status_data[0])
            if num_processed % 100 == 0:
                print("{} Statuses Processed: {}".format(num_processed, datetime.datetime.now()))
                time.sleep(1.5)
                                
        # if there is no next page, we're done.
        if 'paging' in statuses:
            after = statuses['paging']['cursors']['after']
        else:
            has_next_page = False

    print("\nDone!\n{} Statuses Processed in {}".format(
          num_processed, datetime.datetime.now() - scrape_starttime))

#create_db_table()

def identificar(page_id, access_token):
    cont = 0
    after = ''
    base = "https://graph.facebook.com/v2.9"
    node = "/{}/posts".format(page_id)
    parameters = "/?limit={}&access_token={}".format(100, access_token)

    after = '' if after is '' else "&after={}".format(after)
    base_url = base + node + parameters + after
    url = getFacebookPageFeedUrl(base_url)
    
    req = Request(url)

    success = False
    while success is False:
        try:
            response = urlopen(req)
            if response.getcode() == 200:
                success = True
        except Exception as e:
            return 'Null'

i = 0
aux = 0

for i in range(len(pageId)):
    if identificar(pageId[i], access_token) == 'Null':   #Pular as páginas offline
        i +=1
    elif __name__ == '__main__':
        scrapeFacebookPageFeedStatus(pageId[i], access_token)
    aux += 1
    
