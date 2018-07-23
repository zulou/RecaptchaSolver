from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import time, sleep
from recaptcha_exceptions import RecaptchaNotFoundException, ElementNotFoundException, AccessDeniedException
import re

recaptcha_url = 'https://www.google.com/recaptcha/api2/anchor'

RECAPTCHA_RE = ['Select all images with.*\n(.+)',
                'Select all images with.*\n(.+?) or (.+)',
                'Select all images with.*\n(.+)\nClick verify once there are none left',
                'Select all squares with\n(.+)\nIf there are none, click skip']

class RecaptchaSolver:

    def __init__(self, website):
        self.website = website
        self.driver = webdriver.Chrome()

    def connect(self):
        self.driver.get(self.website)

    def switch_to_parent_iframe(self):
        """
        Switches the Selenium Webdriver to the recaptcha's parent iframe
        """
        self.driver.switch_to.default_content()
      
        done = False    
        while not done:
            done = True
            curr_iframes = self.driver.find_elements_by_tag_name('iframe')
            for iframe in curr_iframes:
                src = iframe.get_attribute('src')
                # If recaptcha url is found, return
                if recaptcha_url in src:
                    return
                # If "recaptcha" is in the url, switch iframe and continue from there
                if 'recaptcha' in src:
                    self.driver.switch_to.frame(iframe) 
                    done = False
                    break 
        
        raise RecaptchaNotFoundException('Unable to find recaptcha box') # Unable to find iframe                

    def switch_to_recaptcha_iframe(self):
        """
        Switches the Selenium Webdriver to the recaptcha's iframe
        """        
        self.switch_to_parent_iframe()

        while True:
            curr_iframes = self.driver.find_elements_by_tag_name('iframe')
            for iframe in curr_iframes:
                if recaptcha_url in iframe.get_attribute('src'):
                    self.driver.switch_to.frame(iframe)
                    try:
                        self.driver.find_element_by_class_name('recaptcha-checkbox-checkmark')
                        return                        
                    except NoSuchElementException:
                        self.switch_to_parent_iframe()
     
            raise RecaptchaNotFoundException('Unable to find recaptcha box') # Unable to find iframe

    def click_recaptcha_box(self):
        """
        Finds and clicks recaptcha checkbox
        """       
        self.switch_to_recaptcha_iframe()
        recaptcha_box = self.driver.find_element_by_class_name('recaptcha-checkbox-checkmark')
        recaptcha_box.click()

    def find_recaptcha_element(self, elements, timeout=10):
        """
        Finds and returns the first WebElement object that matches an element from elements

        Args:
            elements: A dictionary where the keys are Selenium By objects and the 
                      values are lists of elements to find using the corresponding By object            
            timeout: The amount of time to search for element until an exception is thrown

        Returns:
            The WebElement object that matches the class name

        Raises:
            ElementNotFoundException: If any element is not found within the specified time
        """ 
        stop = time() + timeout # stop time
        while time() < stop:
            for by, names in elements.items():
                for name in names:
                    # Try to find recaptcha element
                    try:
                        self.switch_to_parent_iframe()
                        # Recaptcha iframe that contains its information
                        recaptcha = self.driver.find_element_by_css_selector('iframe[title="recaptcha challenge"]')
                        self.driver.switch_to.frame(recaptcha)
                        ele = self.driver.find_element(by, name)
                        return ele
                    except NoSuchElementException:
                        # Try next element
                        continue
        raise ElementNotFoundException('Unable to find elements: Timed out after ' + str(timeout) + ' seconds.')

rs = RecaptchaSolver('https://weeband.weebly.com')
rs.connect()
rs.click_recaptcha_box()
try:
    dos = {By.CLASS_NAME: ['rc-doscaptcha-header-text']}
    a = rs.find_recaptcha_element(dos, timeout=2)
    raise AccessDeniedException('Recaptcha detected too many automated responses. Please try again later.')
except ElementNotFoundException:
    pass

task = None

for i in range(1):
    if task:
        WebDriverWait(rs.driver, 10).until(EC.staleness_of(task))
    task = {By.CLASS_NAME: ['rc-imageselect-desc-no-canonical', 'rc-imageselect-desc']}
    task = rs.find_recaptcha_element(task)
    print(task.text, '======================================', sep='\n')

    task = {By.XPATH: ['//*[@id="recaptcha-reload-button"]']}
    task = rs.find_recaptcha_element(task)
    task.click()
    a = rs.driver.find_elements_by_tag_name('strong')
    print(len(a))
    #task = rs.find_recaptcha_element((('recaptcha-verify-button', By.ID),))
    #task = rs.find_recaptcha_element((('rc-image-tile-33', By.CLASS_NAME), ('rc-image-tile-42', By.CLASS_NAME), ('rc-image-tile-44', By.CLASS_NAME)))
    # print(task.get_attribute("src"))

if task:
    WebDriverWait(rs.driver, 10).until(EC.staleness_of(task))
task = {By.CLASS_NAME: ['rc-imageselect-desc-no-canonical', 'rc-imageselect-desc']}
task = rs.find_recaptcha_element(task)
print(task.text, '======================================', sep='\n')