#!/usr/bin/env python
# coding: utf-8

import sys
from selenium.webdriver.common.by import By
import re
from itertools import zip_longest
import sqlite3
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException,TimeoutException
import time

def go_to_page(num_of_page, driver):
    driver.find_element_by_class_name(f"pagination-item-{num_of_page}").click()

def get_page_retry(driver, url, num_retries=3):
    if num_retries > 0:
        try:
            driver.get(url)
            # return driver
        except TimeoutException:
            print('timeout, retrying')
            return get_page_retry(driver, url, num_retries-1)
        else:
            return True
    else:
        return False

def crawler_main(driver):

    try:
        # wait 10 seconds before looking for element
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "tp-bought-root"))
        )
    except:
        print('Unable to locate tp-bought-root on page during 30 seconds')
        driver.quit()

    prices = driver.find_element_by_xpath("//*[@id='tp-bought-root']")
    print('collecting order, price, shipping info...')
    if '交易关闭' in prices.text:
        print("found order closed, please delete it and run again")
        sys.exit(1)
    for index, line in enumerate(prices.text.splitlines()):
        if '订单号' in line:
            order_date, dump = line.split('订单号:')
            dump = dump.lstrip()
            order_id, seller = re.search(r'^(\d+) (.+)', dump).group(1), re.search(r'^(\d+) (.+)', dump).group(2)
            order_date_list.append(order_date)
            order_id_list.append(order_id)
            shop_name_list.append(seller)
            # check the text under line with text 订单号
            order_id = prices.text.splitlines()[index + 1]
            order_id = order_id.split("[交易快照]")[0]
            item_list.append(order_id)
        if '含运费' in line:
            # check the text above 含运费
            price = prices.text.splitlines()[index - 1]
            price_list.append(price)

    elems = driver.find_elements_by_xpath("//a[@href]")
    for elem in elems:
        if "wuliu" in elem.get_attribute("href"):
            shipping_url = elem.get_attribute("href")
            shipping_urls.append(shipping_url)

    #we assumed each item must have a correspoding shipping no, but this may not be true if it's a virtual item

    if len(order_id_list) != len(shipping_urls):
        print('number of order_list is not equal to number of wuliu URL, please check if there is any virtual item or ticket')
        for o,i,s1,s2 in zip_longest(order_id_list, item_list, shop_name_list, shipping_urls, fillvalue='foo'):
            print(o,i,s1,s2)
        sys.exit(1)


if __name__ =="__main__":
    order_id_list = []
    item_list = []
    price_list = []
    shipping_urls = []
    order_date_list = []
    shop_name_list = []

    many = int(input("how many pages to crawl?"))

    chrome_options = webdriver.ChromeOptions()
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)

    conn = sqlite3.connect('taobao.sqlite')
    cur = conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS TAOBAO
        (order_id TEXT PRIMARY KEY, order_date DATETIME, item_id TEXT, price REAL, shop_name TEXT,
        shipping_url TEXT, tracking_id TEXT)''')

    LOGIN_URL = 'https://login.taobao.com/member/login.jhtml?redirectURL=http%3A%2F%2Fbuyertrade.taobao.com%2Ftrade%2Fitemlist%2Flist_bought_items.htm%3Fspm%3D875.7931836%252FB.a2226mz.4.66144265Vdg7d5%26t%3D20110530'
    # PATH = "/usr/lib/chromium-browser/chromedriver"
    PATH = "/Volumes/HDD1/chromedriver_90"


    driver = webdriver.Chrome(executable_path=PATH, options=chrome_options)
    driver.set_page_load_timeout(30)
    driver.get(LOGIN_URL)

    driver.find_element_by_xpath("//*[@id='login']/div[1]/i").click()
    time.sleep(5)
    page_no = 2

    print(f'crawling first page')
    while many:
        crawler_main(driver)
        many -= 1
        if many ==0 :
            break
        else:
            print(f'crawling page number: {page_no} ')
        go_to_page(page_no, driver)
        page_no += 1
        time.sleep(10)

    print(item_list)
    print('updating database..')
    for order_id, order_date, item_id, price, shop_name, shipping_url in zip(order_id_list, order_date_list, item_list, price_list, shop_name_list, shipping_urls):
        cur.execute('INSERT OR IGNORE INTO TAOBAO (order_id, order_date, item_id, price, shop_name, shipping_url) VALUES ( ?, ?, ?, ?, ?, ?)',
                    (order_id, order_date, item_id, price, shop_name, shipping_url))

    conn.commit()
    print('database commited')

    cur.execute('SELECT shipping_url FROM TAOBAO WHERE TRACKING_ID ISNULL')
    try:
        tracking_urls = cur.fetchall()
    except:
        print("No unretrived tracking URL found")

    tracking_dict = {}

    for each_item in tracking_urls:
        tracking_url = each_item[0]
        get_page_retry(driver, tracking_url)
        try:
            WebDriverWait(driver, 30).until(EC.title_contains("物流详情"))
            shipping_no = driver.find_element_by_class_name("order-row").text
            shipping_no = shipping_no.split("客服电话")[0]
            shipping_no = shipping_no.split("运单号码： ")[-1]
            tracking_dict[tracking_url] = shipping_no

        except NoSuchElementException as e:
            print('Specifical format in taobao wuliu info')
            try:
                driver.find_element_by_class_name("fweight") and driver.find_element_by_id("J_NormalLogistics")
                tracking_dict[
                    tracking_url] = f'运单号码：{driver.find_element_by_class_name("fweight").text} {driver.find_element_by_id("J_NormalLogistics").text}'
            except:
                tracking_dict[tracking_url] = 'non-standard shipping info'
        except TimeoutException:
            tracking_dict[tracking_url] = 'timeout'
        finally:
            print(f'{tracking_url} done')

    for url, track_info in tracking_dict.items():
        cur.execute('UPDATE TAOBAO SET tracking_id=? WHERE shipping_url=?', (track_info, url))
    conn.commit()
    print('updating db completed')
    driver.close()
    conn.close()
