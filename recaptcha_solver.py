import io
import numpy as np
import re
import requests
from PIL import Image
from recaptcha_exceptions import RecaptchaNotFoundException, ElementNotFoundException, AccessDeniedException
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from time import time, sleep

recaptcha_url = 'https://www.google.com/recaptcha/api2/anchor'

RECAPTCHA_RE = ['Select all images with.*\n(.+)',
                'Select all images with.*\n(.+?) or (.+)',
                'Select all images with.*\n(.+)\nClick verify once there are none left',
                'Select all squares with\n(.+)\nIf there are none, click skip']

class RecaptchaSolver:

    def __init__(self, website):
        self.website = website
        options = webdriver.ChromeOptions()
        options.add_argument('--incognito')
        options.add_argument('--start-maximized')
        self.driver = webdriver.Chrome(options=options)

    def connect(self):
        self.driver.get(self.website)

    def switch_to_parent_iframe(self):
        """
        Switches the Selenium Webdriver to the recaptcha's parent iframe

        Raises:
            RecaptchaNotFoundException: If the parent iframe is not found
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
        
        Raises:
            RecaptchaNotFoundException: If the recaptcha iframe is not found
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

    def start_challenge(self):
        """
        Clicks recaptcha checkbox to start challenge
        """       
        self.switch_to_recaptcha_iframe()
        recaptcha_box = self.driver.find_element_by_class_name('recaptcha-checkbox-checkmark')
        recaptcha_box.click()

    def find_recaptcha_element(self, elements_dict, timeout=10):
        """
        Finds and returns the first WebElement object that matches an element from elements

        Args:
            elements_dict: A dictionary where the keys are Selenium By objects and the 
                           values are lists of elements to find using the corresponding By object            
            timeout: The amount of time to search for element until an exception is thrown

        Returns:
            The WebElement object that matches the class name

        Raises:
            ElementNotFoundException: If any element is not found within the specified time
        """ 
        stop = time() + timeout # stop time
        while time() < stop:
            for by, names in elements_dict.items():
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

    def split_images(self, images, rows, cols):
        """
        Splits images into a number of equal parts specified by the parameter values

        Args:
            images: Image to split as a numpy array          
            rows: Number of rows to split image into
            cols: Number of columns to split image into

        Returns:
            An array containing the split images as numpy arrays in row major order
        """ 
        split_images = []
        for row in np.split(images, rows, axis=1): # Split into rows
            for col in np.split(row, cols, axis=2): # Split rows into columns
                split_images.append(col)
        return split_images

    def solve_recaptcha(self):
        """
        Solves recaptcha

        Raises:
            AccessDeniedException: If recaptcha detection system denies access 
        """         
        # Check to see presence of recaptcha denial message
        try:
            dos = {By.CLASS_NAME: ['rc-doscaptcha-header-text']}
            self.find_recaptcha_element(dos, timeout=2)
            # Message was found
            raise AccessDeniedException('Recaptcha detected too many automated responses. Please try again later.')
        except ElementNotFoundException:
            # Message not found. Proceed to solving recaptcha
            pass

        task = None
        for i in range(1):
            if task:
                WebDriverWait(self.driver, 10).until(EC.staleness_of(task))
            task = {By.CLASS_NAME: ['rc-imageselect-desc-no-canonical', 'rc-imageselect-desc']}
            # Recaptcha challenge to solve
            task = self.find_recaptcha_element(task).text
            print(task, '======================================', sep='\n')
            
            recaptcha = {By.TAG_NAME: ['img']}
            img = self.find_recaptcha_element(recaptcha)
            url = img.get_attribute('src')
            
            data = requests.get(url).content
            recaptcha_images = Image.open(io.BytesIO(data))   
            arr = np.array(recaptcha_images)

            # Last 2 characters of class tag are dimensions of where to split images
            dim = img.get_attribute('class')[-2:] 
            rows = int(dim[0])
            cols = int(dim[1])

            # imgs = self.split_images(recaptcha_images)

            #task = {By.XPATH: ['//*[@id="recaptcha-reload-button"]']}
            #task = self.find_recaptcha_element(task)
            #task.click()

            #task = {By.ID: ['recaptcha-verify-button']}
            #task = self.find_recaptcha_element(task)
            # print(task.get_attribute("src"))

rs = RecaptchaSolver('https://weeband.weebly.com')
rs.connect()
rs.start_challenge()
rs.solve_recaptcha()