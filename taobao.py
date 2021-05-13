#!/usr/bin/env python
# coding: utf-8

import sys
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException,TimeoutException


import time
chrome_options = webdriver.ChromeOptions()
prefs = {"profile.managed_default_content_settings.images": 2}
chrome_options.add_experimental_option("prefs", prefs)

def get_page_retry(driver, url, num_retries=3):
    if num_retries > 0:
        try:
            driver.get(url)
        except TimeoutException:
            print('timeout, retrying')
            return get_page_retry(driver, url, num_retries-1)
        else:
            return True
    else:
        return False

def crawler_main_page(driver, order_list, item_list, price_list, output_dict):

    prices = driver.find_element_by_xpath("//*[@id='tp-bought-root']")
    print('collecting order and price info...')
    for index, line in enumerate(prices.text.splitlines()):
        if '订单号' in line:
            order_list.append(line)
            #check the text under 订单号
            order_id = prices.text.splitlines()[index + 1]
            order_id = order_id.split("[交易快照]")[0]
            item_list.append(order_id)
        if '含运费' in line:
            # check the text above 含运费
            price = prices.text.splitlines()[index - 1]
            price_list.append(price)
            output_dict[order_id] = [price]

    print('collecting shipping info...')
    elems = driver.find_elements_by_xpath("//a[@href]")

    wuliu_urls = []
    for elem in elems:
        if "wuliu" in elem.get_attribute("href"):
            wuliu_url = elem.get_attribute("href")
            wuliu_urls.append(wuliu_url)
    if len(order_list) != len(wuliu_urls):
        print('number of order_list is not equal to number of wuliu URL, please check')
        sys.exit(1)
    for url,key in zip(wuliu_urls, output_dict.keys()):
        # print(url)
        # print(key)
        print(f'working on wuliu url {url}... ', end=' ')
        try:
            load_result = get_page_retry(driver, url)
            if load_result:
                try:
                    WebDriverWait(driver, 10).until(EC.title_contains("物流详情"))
                    shipping_no = driver.find_element_by_class_name("order-row").text
                    shipping_no = shipping_no.split("客服电话")[0]
                    # print('shipping number', shipping_no)
                    output_dict[key].append(shipping_no)
                except NoSuchElementException:
                    print('specifical format in taobao wuliu info', e)
                    if driver.find_element_by_class_name("fweight").text and driver.find_element_by_id(
                            "J_NormalLogistics").text:
                        output_dict[key].append(f'运单号码：{driver.find_element_by_class_name("fweight").text} {driver.find_element_by_id("J_NormalLogistics").text}')
                    else:
                        output_dict[key].append(f'not standard shipping info from {url}')
                finally:
                    print('done')
            else:
                print('failed')
                output_dict[key].append(f'unable to load page for {url}')
        except Exception as e:
            print(f'processing wuliu info error {e}')
            sys.exit(1)
        time.sleep(1)
    # Go back to 已买到的宝贝 after all wuliu page are done
    get_page_retry(driver, 'https://buyertrade.taobao.com/trade/itemlist/list_bought_items.htm')
    return order_list, item_list, price_list

def go_to_page(num_of_page, driver):
    driver.find_element_by_class_name(f"pagination-item-{num_of_page}").click()

def crawler_page(num_of_page, driver, order_list, item_list, price_list, output_dict):
    crawler_main_page(driver, order_list, item_list, price_list, output_dict)
    go_to_page(int(num_of_page)+1, driver)

def main():
    order_list = []
    item_list = []
    price_list = []
    output_dict = {}

    #change this based on your OS, this is based on linux
    PATH = "/usr/lib/chromium-browser/chromedriver"

    driver = webdriver.Chrome(executable_path=PATH, options=chrome_options)
    driver.set_page_load_timeout(10)
    get_page_retry(driver,
        'https://login.taobao.com/member/login.jhtml?redirectURL=http%3A%2F%2Fbuyertrade.taobao.com%2Ftrade%2Fitemlist%2Flist_bought_items.htm%3Fspm%3D875.7931836%252FB.a2226mz.4.66144265Vdg7d5%26t%3D20110530'                    )
    driver.find_element_by_xpath("//*[@id='login']/div[1]/i").click()

    try:
        WebDriverWait(driver, 30).until(EC.title_contains("已买到的宝贝"))
    except Exception as e:
        print(f'timeout for 已买到的宝贝 page {e}')


    #looping how many pages of 已买到的宝贝
    for num_of_page in range(1, 2):
        if num_of_page == 1:
            order_list, item_list, price_list = crawler_main_page(driver, order_list, item_list,
                                                                price_list, output_dict )
            print(f'page 1 completed')
        else:
            crawler_page(num_of_page, driver, order_list, item_list, price_list,output_dict)
            print(f'page {num_of_page + 1} completed')
            time.sleep(6)

    for k,v in output_dict.items():
        print(k, v)

if __name__ =="__main__":
    main()