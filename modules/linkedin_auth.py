"""
modules/linkedin_auth.py
Handles LinkedIn login authentication
"""

import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class LinkedInAuth:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger('LinkedInBot.Auth')
        self.driver = None
        
    def _init_driver(self):
        """Initialize Chrome WebDriver with appropriate options"""
        options = webdriver.ChromeOptions()
        
        # Add options to appear more human-like
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Optional headless mode
        if self.config['automation_settings'].get('headless', False):
            options.add_argument('--headless')
        
        options.add_argument('--start-maximized')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return self.driver
    
    def login(self):
        """
        Login to LinkedIn using credentials from config
        Returns WebDriver instance
        """
        self.logger.info("Initializing browser...")
        driver = self._init_driver()
        
        try:
            self.logger.info("Navigating to LinkedIn login page...")
            driver.get("https://www.linkedin.com/login")
            
            wait = WebDriverWait(driver, 10)
            
            # Enter email
            self.logger.debug("Entering email...")
            email_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
            email_field.send_keys(self.config['linkedin_credentials']['email'])
            time.sleep(0.5)
            
            # Enter password
            self.logger.debug("Entering password...")
            password_field = driver.find_element(By.ID, "password")
            password_field.send_keys(self.config['linkedin_credentials']['password'])
            time.sleep(0.5)
            
            # Click sign in
            self.logger.debug("Clicking sign in button...")
            sign_in_button = driver.find_element(By.XPATH, "//button[@type='submit']")
            sign_in_button.click()
            
            # Wait for login to complete
            self.logger.info("Waiting for login to complete...")
            time.sleep(5)
            
            # Check if we need to handle verification
            try:
                if "checkpoint" in driver.current_url or "challenge" in driver.current_url:
                    self.logger.warning("⚠ LinkedIn security checkpoint detected!")
                    self.logger.warning("Please complete the verification manually in the browser.")
                    input("Press Enter after completing verification...")
            except:
                pass
            
            # Verify login success
            if "feed" in driver.current_url or "mynetwork" in driver.current_url:
                self.logger.info("✓ Login successful!")
                return driver
            else:
                raise Exception("Login may have failed. Please check credentials.")
                
        except TimeoutException:
            self.logger.error("Login timeout - elements not found")
            raise
        except Exception as e:
            self.logger.error(f"Login failed: {str(e)}")
            driver.quit()
            raise