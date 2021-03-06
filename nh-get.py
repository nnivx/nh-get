#!/usr/bin/env pypy3
import requests     
import lxml.html
import os, sys      # downloading
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from collections import namedtuple

def get_document(url):
    """Returns the document from given url.
    
    Raises requests.exceptions.RequestException
    """
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    return lxml.html.fromstring(r.content)

def get_image_url(img):
    """Gets the image url from <img>
    """
    # element['data-src'] and element.get('data-src') doesn't work
    for k, v in img.items():
        if k == 'data-src':
            # https://t.nhentai.net/galleries/<gallerycode>/<page#>t.<extension>
            # https://i.nhentai.net/galleries/<gallerycode>/<page#>.<extension>
            return v[:8] + 'i' + v[9:32] + v[32:].replace('t.', '.', 1)

Sauce = namedtuple('Sauce', 'title pages tags artists url image_urls')

def get(code) -> Sauce:
    """Gets the sauce from nhentai codes.
    """
    url = 'https://nhentai.net/g/%s/' % code
    doc = get_document(url)
    info = doc.xpath('//div[@id="info"]')[0]

    #title = info[0].text
    #pages = int( info[3].text.split()[0] )
    title = info.xpath('./h1/text()')[0]
    pages = int( info.xpath('./div[contains(text(), "pages")]')[0].text.split()[0] )
    
    tags = [ tag.text[:-1] for tag in info.xpath('.//div[contains(text(), "Tags:")]')[0].getchildren()[0] ]
    artists = [ tag.text[:-1] for tag in info.xpath('.//div[contains(text(), "Artists:")]')[0].getchildren()[0] ]

    # get the gallery codes by checking the thumbnails
    # this returns <a> which contains <img>
    image_urls = [ get_image_url(a[0]) for a in doc.xpath('//a[@class="gallerythumb"]') ]

    return Sauce(title, pages, tags, artists, url, image_urls)

def download(code):
    sauce = get(code)
    
    print('Downloading:', sauce.title)
    print('Pages:', sauce.pages)
    print('Tags:', ', '.join(sauce.tags))
    print('Artists:', ', '.join(sauce.artists))

    with tempfile.TemporaryDirectory() as temp_dir:
        url_list = Path(temp_dir).joinpath('files_list')

        # write the urls into file for download 
        with open(url_list, 'w') as file:
            for url in sauce.image_urls:
                file.write(url)
                file.write('\n')
        
        # download files
        subprocess.run(['aria2c',
            '-d', temp_dir,
            '-i', url_list,
            '-q',
            ])
        
        # fix image file extension cos it's sometimes wrong
        subprocess.run(['fixImgExt.sh',
            '-d', temp_dir,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT)
        files = [ x.name for x in Path(temp_dir).glob('*') if x.is_file() and x != url_list ]

        # save zip
        os.chdir(temp_dir)

        # FIX: replace slashes with DIVISION_SLASH
        cleanpath = (sauce.title + '.cbz').replace('/', '\u2215')

        zip_name = dest_dir.joinpath(cleanpath)
        if not zip_name.parent.is_dir():
            raise IOError('Target "%s" does not exist' % zip_name.parent)

        with ZipFile(zip_name, 'w', compression=ZIP_DEFLATED) as zf: 
            for filename in files:
                zf.write(filename)
    

if __name__ == '__main__':
    dest_dir = Path.home().joinpath('Downloads')
    
    for code in sys.argv[1:]:
        try:
            download(code)
            print()
        except requests.exceptions.RequestException:
            # TODO url hardcoded in different places
            print('Cannot get https://nhentai.net/g/%s/' % code, file=sys.stderr)
        print()
