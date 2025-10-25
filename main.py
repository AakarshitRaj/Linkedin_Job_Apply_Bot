"""
LinkedIn Job Application Automation Bot
Main entry point for the automation system
"""

import json
import logging
import time
from datetime import datetime
from modules.logger_config import setup_logger
from modules.linkedin_auth import LinkedInAuth
from modules.job_search import JobSearch
from modules.easy_apply import EasyApplyBot
from modules.config_manager import ConfigManager

def main():
    # Setup logging
    logger = setup_logger()
    logger.info("=" * 80)
    logger.info("LinkedIn Job Application Bot Started")
    logger.info(f"Session started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    try:
        # Load configuration
        config_manager = ConfigManager('config.json')
        config = config_manager.load_config()
        logger.info("Configuration loaded successfully")
        
        # Initialize authentication
        auth = LinkedInAuth(config)
        driver = auth.login()
        logger.info("LinkedIn login successful")
        
        # Initialize job search
        job_search = JobSearch(driver, config)
        
        # Initialize Easy Apply bot
        easy_apply_bot = EasyApplyBot(driver, config, logger)
        
        # Search and apply in real-time (no collecting, immediate action)
        applied_count = 0
        jobs_processed = 0
        max_jobs = config['job_search'].get('max_jobs', 20)
        
        keywords = config['job_search']['keywords']
        
        for keyword in keywords:
            if jobs_processed >= max_jobs:
                break
                
            logger.info(f"Searching for: {keyword}")
            
            # Navigate to search page
            jobs_found = job_search.search_and_apply_realtime(
                keyword, 
                easy_apply_bot, 
                max_jobs - jobs_processed
            )
            
            applied_count += jobs_found['applied']
            jobs_processed += jobs_found['processed']
            
            logger.info(f"Processed {jobs_found['processed']} jobs for '{keyword}', applied to {jobs_found['applied']}")
        
        # Final summary
        logger.info("=" * 80)
        logger.info(f"Automation completed!")
        logger.info(f"Total jobs processed: {len(job_listings)}")
        logger.info(f"Successfully applied: {applied_count}")
        logger.info(f"Session ended at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)
        
    except KeyboardInterrupt:
        logger.warning("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error occurred: {str(e)}", exc_info=True)
    finally:
        try:
            driver.quit()
            logger.info("Browser closed successfully")
        except:
            pass

if __name__ == "__main__":
    main()