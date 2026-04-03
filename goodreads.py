#!/usr/bin/python3

import requests 
from bs4 import BeautifulSoup

headers = {
          'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.5',
      }
r = requests.get("https://www.goodreads.com/search?utf8=%E2%9C%93&query=lord+of+the+rings", headers=headers, timeout=10)

soup = BeautifulSoup(r.text, "html.parser")
books = soup.find("body").select(".tableList tr")

with open("books.txt", "w") as fp:
    for book in books:
        print(book.find_all('td')[1].find(class_="bookTitle").find(itemprop="name").string)
        print(book.find_all('td')[1].find(class_="authorName").find(itemprop="name").string)
        print(" ")

        fp.write(f"{book.find_all('td')[1].find(class_="bookTitle").find(itemprop="name").string}\n")
        fp.write(f"{book.find_all('td')[1].find(class_="authorName").find(itemprop="name").string}\n")
        fp.write('----------\n')

