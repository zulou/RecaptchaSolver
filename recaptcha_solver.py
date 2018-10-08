import io
import numpy as np
import os
import re
import requests

from image_detection import predict
from PIL import Image
from recaptcha_exceptions import AccessDeniedException, ElementNotFoundException, RecaptchaNotFoundException
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from time import sleep, time

RECAPTCHA_URL = 'https://www.google.com/recaptcha/api2/anchor'

RECAPTCHA_RE = ['Select all images with.*\n(.+)\nClick verify once there are none left',
                'Select all images with.*\n(.+?) or (.+)',
                'Select all images with.*\n(.+)',
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
                if RECAPTCHA_URL in src:
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
                if RECAPTCHA_URL in iframe.get_attribute('src'):
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

    def find_recaptcha_element(self, elements_dict, all_elements=False, timeout=10):
        """
        Returns the first match to an element in elements_dict as a WebElement object.
        If all_elements is true, a list of all elements found by the first match is returned.

        Args:
            elements_dict: A dictionary where the keys are Selenium By objects and the 
                           values are lists of elements to find using the corresponding By object            
            timeout: The amount of time to search for element until an exception is thrown
            all_elements: Whether or not to find all objects that match an element

        Returns:
            The WebElement object or a list of WebElement objects that match an element name

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
                        return self.driver.find_elements(by, name) if all_elements else self.driver.find_element(by, name) 
                    except NoSuchElementException:
                        # Try next element
                        continue       
        raise ElementNotFoundException('Unable to find elements: Timed out after ' + str(timeout) + ' seconds.')

    def download_images(self, index):
            recaptcha = {By.TAG_NAME: ['img']}
            img = self.find_recaptcha_element(recaptcha, all_elements=True)[index]
            url = img.get_attribute('src')

            dim = img.get_attribute('class')[-2:] 
            rows = int(dim[0])
            cols = int(dim[1])    
            
            # Download recaptcha images to memory
            data = requests.get(url).content
            recaptcha_images = Image.open(io.BytesIO(data))  

            # Convert image to numpy array
            images_arr = np.array(recaptcha_images)                   
            return (images_arr, rows, cols)
    
    def click_tiles(self, predictions, cols):
        for pred in predictions:
            index = pred[0] * cols + pred[1]
            self.driver.find_elements_by_tag_name('td')[index].click()
            sleep(0.5)
    
    def solve_challenge(self, images, task, rows, cols):
        task_type = -1
        labels = None # Class labels to find for recaptcha challenge
        for idx, val in enumerate(RECAPTCHA_RE):
            recaptcha_re = re.search(val, task)
            if recaptcha_re:
                task_type = idx
                labels = recaptcha_re.groups()
                break
               
        if task_type == 0:
            return self.solve_dynamic_images_challenge(images, labels, rows, cols)
        elif task_type == 1 or task_type == 2 or task_type == 3:
            return self.solve_static_images_challenge(images, labels, rows, cols)
        else:
            print('Unable to recognize challenge')
            return False
    
    def solve_static_images_challenge(self, images, labels, rows, cols):
        predictions = predict(images, labels, rows, cols)
        self.click_tiles(predictions, cols)
        return predictions == []
    
    def download_dynamic_images(self, predictions, dims, cols):
        height = dims[0] * len(predictions)
        width = dims[1]
        new_imgs = np.zeros((height, width, dims[2]))
        for idx, pred in enumerate(predictions):
            index = pred[0] * cols + pred[1]
            new_img, _, _ = self.download_images(index)
            new_imgs[idx*dims[0] : (idx+1)*dims[0]] = new_img
        return new_imgs
    
    def solve_dynamic_images_challenge(self, images, labels, rows, cols):
        predictions = predict(images, labels, rows, cols)
        if predictions:
            self.click_tiles(predictions, cols)
        else:
            return False

        # While predictions is not empty
        while predictions:
            print(predictions)
            new_predictions = []
            sleep(5) # wait for new challenge to load
            height = int(images.shape[0] / rows)
            width = int(images.shape[1] / cols)
            dims = (height, width, images.shape[2])
            new_imgs = self.download_dynamic_images(predictions, dims, cols)
            new_prediction = predict(new_imgs, labels, len(predictions), 1)
            for pred in new_prediction:
                new_prediction = [predictions[pred[0]]]
                self.click_tiles(new_prediction, cols)
                new_predictions.append(new_prediction[0])
            predictions = new_predictions  
        
        return True
                      
    
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

        time_in = time()
        done = False
        while not done:          
            task = {By.CLASS_NAME: ['rc-imageselect-desc-no-canonical', 'rc-imageselect-desc']}
            # Recaptcha challenge to solve
            task = self.find_recaptcha_element(task).text
            print(task, '======================================', sep='\n')

            labels = None
            for _, val in enumerate(RECAPTCHA_RE):
                recaptcha_re = re.search(val, task)
                if recaptcha_re:
                    labels = recaptcha_re.groups()
                    break
            imgs, rows, cols = self.download_images(0)                   
            
            if self.solve_challenge(imgs, task, rows, cols): # if able to solve              
                verify = {By.ID: ['recaptcha-verify-button']}
                verify = self.find_recaptcha_element(verify)
                verify.click()

                try:
                    error = {By.CLASS_NAME: ['rc-imageselect-error-select-more']}
                    text = self.find_recaptcha_element(error, timeout=2).text
                    if text == 'Please select all matching images.':
                        new_recaptcha = {By.XPATH: ['//*[@id="recaptcha-reload-button"]']}
                        new_recaptcha = self.find_recaptcha_element(new_recaptcha)
                        new_recaptcha.click()
                        print('Unable to solve. Skipping challenge.')
                        sleep(2)
                        continue
                except ElementNotFoundException:
                    pass  

            else: #if not able to solve
                new_recaptcha = {By.XPATH: ['//*[@id="recaptcha-reload-button"]']}
                new_recaptcha = self.find_recaptcha_element(new_recaptcha)
                new_recaptcha.click()

            sleep(2) 

            self.switch_to_recaptcha_iframe()
            status = self.driver.find_element_by_xpath('//*[@id="recaptcha-anchor"]').get_attribute('aria-checked')
            done = True if status == 'true' else False
        print(time() - time_in)

rs = RecaptchaSolver('https://patrickhlauke.github.io/recaptcha/')
rs.connect()
rs.start_challenge()
rs.solve_recaptcha()