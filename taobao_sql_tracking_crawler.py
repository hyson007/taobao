import sqlite3
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException,TimeoutException
import time


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

conn = sqlite3.connect('taobao.sqlite')
cur = conn.cursor()
cur.execute('SELECT shipping_url FROM TAOBAO WHERE TRACKING_ID ISNULL')
try:
    tracking_urls = cur.fetchall()
except:
    print("No unretrived tracking URL found")

LOGIN_URL = 'https://login.taobao.com/member/login.jhtml?redirectURL=http%3A%2F%2Fbuyertrade.taobao.com%2Ftrade%2Fitemlist%2Flist_bought_items.htm%3Fspm%3D875.7931836%252FB.a2226mz.4.66144265Vdg7d5%26t%3D20110530'



prefs = {"profile.managed_default_content_settings.images": 2}
PATH = "E:\chromedriver_win32\chromedriver.exe"
chrome_options = webdriver.ChromeOptions()
chrome_options.add_experimental_option("prefs", prefs)
# chrome_options.add_argument("--disable-extensions")
# chrome_options.add_argument("--disable-gpu")

driver = webdriver.Chrome(executable_path=PATH, options=chrome_options)
driver.set_page_load_timeout(30)

tracking_dict = {}

driver.get(LOGIN_URL)
# driver = get_page_retry(driver, LOGIN_URL)
driver.find_element_by_xpath("//*[@id='login']/div[1]/i").click()
time.sleep(10)

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
            tracking_dict[tracking_url] = f'运单号码：{driver.find_element_by_class_name("fweight").text} {driver.find_element_by_id("J_NormalLogistics").text}'
        except:
            tracking_dict[tracking_url] = 'non-standard shipping info'
    except TimeoutException:
        tracking_dict[tracking_url] = 'timeout'
    finally:
        print(f'{tracking_url} done')


for url, track_info in tracking_dict.items():
    cur.execute('UPDATE TAOBAO SET tracking_id=? WHERE shipping_url=?',(track_info, url))
conn.commit()
print('updating db completed')
driver.close()
