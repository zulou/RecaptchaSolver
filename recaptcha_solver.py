import io
import numpy as np
import re
import requests
from image_classification import predict
from PIL import Image
from recaptcha_exceptions import AccessDeniedException, ElementNotFoundException, RecaptchaNotFoundException
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from time import sleep, time

recaptcha_url = 'https://www.google.com/recaptcha/api2/anchor'

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
            An array where each element is a row array of images.
            Each row contains an equal number of images as numpy arrays 
        """ 
        return [np.split(row, cols, axis=1) for row in np.split(images, rows, axis=0)]
    
    def click_tiles(self, predictions, rows, cols):
        for pred in predictions:
            index = pred[0] * cols + pred[1]
            self.driver.find_elements_by_tag_name('td')[index].click()
    
    def solve_challenge(self, images, task):
        task_type = -1
        labels = None # Class labels to find for recaptcha challenge
        for i in range(len(RECAPTCHA_RE)):
            recaptcha_re = re.search(RECAPTCHA_RE[i], task)
            if recaptcha_re:
                task_type = i
                labels = recaptcha_re.groups()
        
        if task_type == 0:
            self.solve_dynamic_images_challenge(images, labels)
        elif task_type == 1:
            self.solve_static_images_challenge_2(images, labels)
        elif task_type == 2 or task_type == 3:
            self.solve_static_images_challenge_1(images, labels)
        else:
            print('Unable to recognize challenge')
            return
    
    def solve_static_images_challenge_1(self, images, labels):
        predictions = predict(images, labels, 0.05)
        self.click_tiles(predictions, len(images), len(images[0]))

    def solve_static_images_challenge_2(self, images, labels):
        predictions = predict(images, labels, 0.05)
        self.click_tiles(predictions, len(images), len(images[0]))
    
    def solve_dynamic_images_challenge(self, images, labels):
        predictions = predict(images, labels, 0.05)
        self.click_tiles(predictions, len(images), len(images[0]))
    
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
        done = False
        while not done:
            if task:
                WebDriverWait(self.driver, 10).until(EC.staleness_of(task))
            
            recaptcha = {By.TAG_NAME: ['img']}
            img = self.find_recaptcha_element(recaptcha)
            url = img.get_attribute('src')
            
            # Download recaptcha images to memory
            data = requests.get(url).content
            recaptcha_images = Image.open(io.BytesIO(data))  

            # Last 2 characters of class tag are dimensions of where to split images
            dim = img.get_attribute('class')[-2:] 
            rows = int(dim[0])
            cols = int(dim[1])

            # Resize image
            recaptcha_images = recaptcha_images.resize((331*cols, 331*rows), Image.ANTIALIAS)
            # Convert image to numpy array
            images_arr = np.array(recaptcha_images)          
            imgs = self.split_images(images_arr, rows, cols)
            
            """
            # Save images as jpgs
            for j in range(rows): 
                for k in range(cols):
                    im = Image.fromarray(imgs[j][k])
                    im.save(str(j) + str(k) + ".jpeg")
            """

            task = {By.CLASS_NAME: ['rc-imageselect-desc-no-canonical', 'rc-imageselect-desc']}
            # Recaptcha challenge to solve
            task = self.find_recaptcha_element(task).text
            print(task, '======================================', sep='\n')

            self.solve_challenge(imgs, task)

            #task = {By.XPATH: ['//*[@id="recaptcha-reload-button"]']}
            #task = self.find_recaptcha_element(task)
            #task.click()

            sleep(5)

            verify = {By.ID: ['recaptcha-verify-button']}
            verify = self.find_recaptcha_element(verify)
            verify.click()

            self.switch_to_parent_iframe()
            sleep(2)
            status = self.driver.find_element_by_xpath('//*[@id="recaptcha-anchor"]').get_attribute('aria-checked')
            done = True if status == 'true' else False

rs = RecaptchaSolver('https://weeband.weebly.com')
rs.connect()
rs.start_challenge()
rs.solve_recaptcha()