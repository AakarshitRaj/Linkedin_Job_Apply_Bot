"""
modules/job_search.py
Handles job searching and collecting job listings
"""

import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class JobSearch:
    def __init__(self, driver, config):
        self.driver = driver
        self.config = config
        self.logger = logging.getLogger('LinkedInBot.JobSearch')
        
    def search_and_apply_realtime(self, keyword, easy_apply_bot, max_jobs):
        """
        Search for jobs and apply in real-time (no collecting, immediate action)
        This is MUCH faster as it doesn't wait to collect all jobs first
        """
        location = self.config['job_search'].get('location', '')
        scroll_pause = self.config['automation_settings'].get('scroll_pause', 2)
        
        applied_count = 0
        processed_count = 0
        
        try:
            # Build search URL with Easy Apply filter
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={keyword.replace(' ', '%20')}"
            
            if location:
                search_url += f"&location={location.replace(' ', '%20')}"
            
            # Add Easy Apply filter
            search_url += "&f_AL=true"
            
            self.logger.debug(f"Navigating to: {search_url}")
            self.driver.get(search_url)
            time.sleep(3)
            
            # Wait for job list to load
            wait = WebDriverWait(self.driver, 15)
            
            job_list_selectors = [
                "ul.scaffold-layout__list-container",
                ".jobs-search-results__list",
                "ul.jobs-search__results-list",
                ".scaffold-layout__list"
            ]
            
            job_list = None
            for selector in job_list_selectors:
                try:
                    job_list = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    break
                except TimeoutException:
                    continue
            
            if not job_list:
                self.logger.warning("Could not find job list")
                return {'processed': 0, 'applied': 0}
            
            time.sleep(2)
            
            # Process jobs in real-time as we scroll
            seen_jobs = set()
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            while processed_count < max_jobs and scroll_attempts < max_scroll_attempts:
                # Find job cards on current view
                job_card_selectors = [
                    "li.scaffold-layout__list-item",
                    "li.jobs-search-results__list-item",
                    "div.job-card-container",
                    ".jobs-search-results-list__list-item"
                ]
                
                job_cards = []
                for selector in job_card_selectors:
                    job_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if job_cards:
                        break
                
                # Process each visible job immediately
                for job_card in job_cards:
                    if processed_count >= max_jobs:
                        break
                    
                    try:
                        # Get job ID to avoid duplicates
                        job_id = job_card.get_attribute('data-job-id') or \
                                 job_card.get_attribute('data-occludable-job-id') or \
                                 job_card.get_attribute('id')
                        
                        if job_id and job_id in seen_jobs:
                            continue
                        
                        if job_id:
                            seen_jobs.add(job_id)
                        
                        processed_count += 1
                        self.logger.info(f"\n[{processed_count}/{max_jobs}] Processing job...")
                        
                        # Apply immediately (no waiting!)
                        result = easy_apply_bot.process_job(job_card)
                        
                        if result:
                            applied_count += 1
                            self.logger.info(f"✓ Applied! Total: {applied_count}")
                        
                        time.sleep(0.5)  # Small delay between jobs
                        
                    except Exception as e:
                        self.logger.debug(f"Error processing job card: {str(e)}")
                        continue
                
                # Scroll to load more jobs
                if processed_count < max_jobs:
                    last_height = self.driver.execute_script("return document.body.scrollHeight")
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(scroll_pause)
                    
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        scroll_attempts += 1
                    else:
                        scroll_attempts = 0
            
            return {'processed': processed_count, 'applied': applied_count}
            
        except Exception as e:
            self.logger.error(f"Error in real-time search: {str(e)}")
            return {'processed': processed_count, 'applied': applied_count}
    
    def search_jobs(self):
        """
        Search for jobs based on keywords from config
        Returns list of job listing elements
        """
        keywords = self.config['job_search']['keywords']
        location = self.config['job_search'].get('location', '')
        max_jobs = self.config['job_search'].get('max_jobs', 50)
        
        all_jobs = []
        
        for keyword in keywords:
            self.logger.info(f"Searching for: {keyword}")
            
            try:
                jobs = self._search_keyword(keyword, location, max_jobs)
                all_jobs.extend(jobs)
                self.logger.info(f"Found {len(jobs)} jobs for '{keyword}'")
            except Exception as e:
                self.logger.error(f"Error searching '{keyword}': {str(e)}")
                continue
        
        # Remove duplicates based on job URL
        unique_jobs = self._deduplicate_jobs(all_jobs)
        self.logger.info(f"Total unique jobs found: {len(unique_jobs)}")
        
        return unique_jobs
    
    def _search_keyword(self, keyword, location, max_jobs):
        """Search for a specific keyword and return job listings"""
        try:
            # Build search URL with Easy Apply filter
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={keyword.replace(' ', '%20')}"
            
            if location:
                search_url += f"&location={location.replace(' ', '%20')}"
            
            # Add Easy Apply filter
            search_url += "&f_AL=true"
            
            self.logger.debug(f"Navigating to: {search_url}")
            self.driver.get(search_url)
            time.sleep(3)
            
            # Scroll to load more jobs
            jobs = self._scroll_and_collect_jobs(max_jobs)
            
            return jobs
            
        except Exception as e:
            self.logger.error(f"Error searching for '{keyword}': {str(e)}")
            return []
    
    def _scroll_and_collect_jobs(self, max_jobs):
        """Scroll through job listings and collect job cards"""
        jobs = []
        scroll_pause = self.config['automation_settings'].get('scroll_pause', 2)
        
        try:
            wait = WebDriverWait(self.driver, 15)
            
            # Try multiple selectors for job list (LinkedIn changes these)
            job_list_selectors = [
                "ul.scaffold-layout__list-container",
                ".jobs-search-results__list",
                "ul.jobs-search__results-list",
                ".scaffold-layout__list"
            ]
            
            job_list = None
            for selector in job_list_selectors:
                try:
                    job_list = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    self.logger.debug(f"Found job list with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not job_list:
                self.logger.warning("Could not find job list container")
                return []
            
            time.sleep(3)  # Let jobs load
            
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            while len(jobs) < max_jobs and scroll_attempts < max_scroll_attempts:
                # Try multiple selectors for job cards
                job_card_selectors = [
                    "li.scaffold-layout__list-item",
                    "li.jobs-search-results__list-item",
                    "div.job-card-container",
                    ".jobs-search-results-list__list-item"
                ]
                
                job_cards = []
                for selector in job_card_selectors:
                    job_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if job_cards:
                        self.logger.debug(f"Found {len(job_cards)} jobs with selector: {selector}")
                        break
                
                # Store new jobs
                for card in job_cards:
                    if card not in jobs:
                        jobs.append(card)
                        if len(jobs) >= max_jobs:
                            break
                
                self.logger.debug(f"Collected {len(jobs)} jobs so far...")
                
                # Scroll down
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(scroll_pause)
                
                # Check if we've reached the bottom
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    scroll_attempts += 1
                else:
                    scroll_attempts = 0
                    last_height = new_height
            
            self.logger.info(f"Successfully collected {len(jobs)} job cards")
            return jobs[:max_jobs]
            
        except TimeoutException:
            self.logger.warning("Timeout while loading job listings")
            return jobs
        except Exception as e:
            self.logger.error(f"Error collecting jobs: {str(e)}")
            return jobs
    
    def _deduplicate_jobs(self, jobs):
        """Remove duplicate jobs based on data-job-id attribute"""
        seen_ids = set()
        unique_jobs = []
        
        for job in jobs:
            try:
                # Try to get job ID from various attributes
                job_id = None
                
                # Try data-job-id
                try:
                    job_id = job.get_attribute('data-job-id')
                except:
                    pass
                
                # Try data-occludable-job-id
                if not job_id:
                    try:
                        job_id = job.get_attribute('data-occludable-job-id')
                    except:
                        pass
                
                # Try id attribute
                if not job_id:
                    try:
                        job_id = job.get_attribute('id')
                    except:
                        pass
                
                # If we found an ID and haven't seen it, add the job
                if job_id:
                    if job_id not in seen_ids:
                        seen_ids.add(job_id)
                        unique_jobs.append(job)
                        self.logger.debug(f"Added job with ID: {job_id}")
                else:
                    # No ID found, include it anyway to be safe
                    unique_jobs.append(job)
                    self.logger.debug("Added job without ID")
                    
            except Exception as e:
                # If any error, include the job anyway
                self.logger.debug(f"Error checking job ID: {str(e)}")
                unique_jobs.append(job)
        
        self.logger.info(f"Deduplication: {len(jobs)} -> {len(unique_jobs)} unique jobs")
        return unique_jobs