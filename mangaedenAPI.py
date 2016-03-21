#!/usr/bin/env python
# -*- coding: utf-8-*-

"""mangaeden.py: a script used to retrieve informations on mangaeden.com


                THANKS TO 
                Mangaeden:      http://www.mangaeden.com/api/
                Alfred-Workflow by deanishe@deanishe.net
                The script is intended for studying porpouse only and as a demo.
                Be careful when using it, and _READ_ the ToS of Mangaeden:
                https://www.mangaeden.com/it/terms/
                Use it as you want, just give me feeddback if you find any bug/issue
                or for asking new features using my email account.
                Just give credit if you want to reuse parts of this code
"""

__author__ = "Emanuele Munafò"
__version__ = "1"
__email__ = "ema.muna95@gmail.com"
__status__ = "Development"

import sys
from workflow import Workflow
from workflow import web
from workflow import notify
from workflow.background import run_in_background, is_running
import argparse
from datetime import date
from urllib import urlretrieve  # Needed for downoad
from threading import BoundedSemaphore

status_val = ["Unknown", "Open", "Closed"]
lang = 0
lang_val = ["en", "it"]

# Used for multithreaded download
gn = 0
sync = BoundedSemaphore()


def main(wf):
    import os

    # Argument parsing configuration
    parser = argparse.ArgumentParser()
    parser.add_argument('--setlang', dest='lang', nargs='?', default=0)
    parser.add_argument('query', nargs='?', default=None)
    args = parser.parse_args(wf.args)
    if args.lang == '1':
        global lang
        lang = 1  # Set global lang
    # Call different functions filtering by argument
    if 'showmanga:' in args.query:  # Search and show list of results
        mid = args.query.split('showmanga:')[1]  # Parse the unique manga id
        search_by_mid(wf, mid)
    elif 'downloadmanga:' in args.query:  # Perform a massive download of selected manga
        mid = args.query.split('downloadmanga:')[1]
        # TODO check if there is at least 1 element
        notify.notify("Background download started!",
                      "Multithreading download started. You will be notified when completed.", sound='Submarine')
        wf.add_item("Download started", "At the end you will be notified in the notification center.",
                    valid=False, arg="", autocomplete="")  # Autocomplete will restore the clear command
        # Run massive download in background (~ subprocess.call)
        run_in_background('download', ['/usr/bin/python', wf.workflowfile('mangaedenAPI.py'), 'dmanga:' + mid])
        wf.send_feedback()
    elif 'dmanga:' in args.query:
        # TODO better error handling while background download is running
        mid = args.query.split('dmanga:')[1]
        download_manga(mid)
    else:
        # Search on mangaeden json list
        query = args.query.lower()
        search_by_query(wf, query)


def search_by_query(wf, query):
    """Search by query in the list of manga

    Show some infos about mangas matching the query
    """

    from threading import Thread
    import os.path

    data = get_json_data()
    i = 0  # Counter of results
    for manga in data['manga']:
        if query in manga['t'].lower() and i < 20:  # Search in the list and show max 20 results
            dstring = "Hits: " + str(manga['h']) + " | "
            dstring += "Status: " + status_val[manga['s']] + " | "
            dstring += "Category:" + ' '.join(manga['c'][0:3])  # Showing max 3 category
            if manga['im']:  # If there is an image
                icon_path = "/tmp/" + manga['im'].replace("/", "")
                if not os.path.isfile(icon_path) and i < 9:  # Multithreaded download for the first 10
                    # covers not already downloaded
                    t = Thread(target=parallel_download, args=(manga['im'],))
                    t.start()
            else:
                icon_path = "icon.png"
            wf.add_item(manga['t'], dstring, arg=manga['i'], valid=False,
                        autocomplete="showmanga:" + manga['i'], icon=icon_path)
            i += 1
    if i == 0:
        wf.add_item("No elements was found!", "Try with an other query...",
                    valid=False, autocomplete=query[:-1], icon="error.png")  # Look at autocomplete :D
    sync.acquire()  # Wait until all the images are downloaded
    wf.send_feedback()
    sync.release()


def search_by_mid(wf, mid):
    """Search by unique id and show infos about chapters"""

    import os.path

    try:
        data = get_json_info(mid)  # Get info about manga thanks to API
    except Exception:
        wf.add_item("Check your internet connection!", "Check later...",
                    valid=False, autocomplete="", icon="error.png")  # Funny ping here?
        wf.send_feedback()
    title = data['title'] + "(" + data['author'] + ")"
    read_url = "http://www.mangaeden.com/" + lang_val[lang] + "/"  # Link to online reader of the specified chapter
    read_url += lang_val[lang] + "-manga/" + data['alias'].lower() + "/"
    icon_path = "/tmp/" + data['image'].replace("/", "")  # Where the icon will be downloaded
    if not os.path.isfile(icon_path):  # If the icon was not download yet, do it
        download_jpg(data['image'])
    wf.add_item(title, "Download all the chapters!", arg=data['alias'], valid=False,
                autocomplete="downloadmanga:" + mid, icon=icon_path)  # First element
    # to do the massive download of the manga (call downloadmanga:)
    for chapter in data['chapters']:
        capn = str(chapter[0])  # Chapter's number 
        cap_num = "Chapter: " + capn
        pub_date = "Publication date: " + date.fromtimestamp(chapter[1]).isoformat()
        reader_url = read_url + capn + "/1/"  # Linking to the online reader featured by MEden
        wf.add_item(cap_num, pub_date, arg=reader_url, valid=True, icon=icon_path)
    # Send output to Alfred
    wf.send_feedback()


def get_json_list():
    """Retrieve json data by url
    
    Return a list of mangas
    """

    api_url = 'https://www.mangaeden.com/api/list/' + str(lang) + '/'
    r = web.get(api_url)
    r.raise_for_status()
    return r.json()


def get_json_info(mid):
    """Retrieve json data by url
    
    Return a list as provided by api when searching for a manga
    """

    api_url = 'https://www.mangaeden.com/api/manga/' + mid + '/'
    r = web.get(api_url)
    r.raise_for_status()
    return r.json()


def get_json_chapter(cid):
    """Retrieve json chapter infos by cid (chapter id)
    
    Return a list as provided by api when searching for a manga
    """

    api_url = 'https://www.mangaeden.com/api/chapter/' + cid + '/'
    r = web.get(api_url)
    r.raise_for_status()
    return r.json()


def download_jpg(image):
    """Download jpg file from given url and saves to /tmp/name.jpg"""

    download_url = "https://cdn.mangaeden.com/mangasimg/" + image
    urlretrieve(download_url, "/tmp/" + image.replace("/", ""))


def parallel_download(iid):
    """Execute parallel downloading"""

    global gn
    gn += 1
    if gn == 1:
        sync.acquire()
    download_jpg(iid)
    gn -= 1
    if gn == 0:
        sync.release()


def download_page(iid, path):
    """Download a specific page by its id"""

    download_url = "https://cdn.mangaeden.com/mangasimg/" + iid
    ext = "." + iid.split(".")[1]
    urlretrieve(download_url, path + ext)


def download_chapter(malias, cnum, cid):
    """Download the nth chapter in a new folder."""

    import os.path
    from threading import Thread

    folder_path = os.path.expanduser("~") + "/" + str(malias) + "/" + str(cnum) + "/"  # ~/<title of manga>/<chapter n>/
    if not os.path.exists(folder_path):  # Should check for internet files for a better error handling
        os.makedirs(folder_path)
        pages = get_json_chapter(cid)['images']
        # Launch multithread for downloading jpg
        for page in pages:
            t = Thread(target=download_page, args=(page[1], folder_path + str(page[0])))  # Page[0] is the n. of chapter
            t.start()
    else:
        # Already downloaded
        pass
    return 0


def download_manga(mid):
    """Download whole manga """
    i = 0
    import os.path

    try:
        data = get_json_info(mid)
        for chapter in data['chapters']:
            i += 1
            download_chapter(data['alias'], chapter[0], chapter[3])
        if i == 0:  # No chapters in this manga!
            notify.notify("Download Failed!", "This manga has no chapters!", sound="Bass")
        else:
            folder_path = os.path.expanduser("~") + "/" + str(data['alias']) + "/"
            notify.notify("Download completed!", "Look at " + folder_path + " folder!", sound='Glass')
    except Exception:
        notify.notify("Download Failed!",
                      "You can restart it!\nYour progress will not be lost!" + folder_path + " folder!")


def get_json_data():
    """Get json data from the api with 10 days caching."""

    if lang == 1:  #  Italian lang.
        data = wf.cached_data('mangalist_ita', get_json_list, max_age=864000)
    else:
        data = wf.cached_data('mangalist_eng', get_json_list, max_age=864000)
    return data


if __name__ == '__main__':
    wf = Workflow()
    sys.exit(wf.run(main))

# Other TODO:
# - Customize the caching time
# - stop current download
# - Improved language handling
# - 
# Known bug:
# None
# Sound:
# Basso for errors
# Glass for end
