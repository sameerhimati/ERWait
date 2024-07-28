import logging

def setup_logger():
    logger = logging.getLogger('hospital_scraper')
    logger.setLevel(logging.INFO)

    # Check if the logger has handlers already
    if not logger.handlers:
        # Create a file handler
        file_handler = logging.FileHandler('hospital_scraper.log')
        file_handler.setLevel(logging.INFO)
        
        # Create a console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create a logging format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add the handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

# Global logger instance
logger = setup_logger()
