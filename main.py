from random import randint

import check
from config import APP_NAME, ENVIRONMENT
from logger import logger
from utils import is_valid_random_number

def main() -> None:
    print(APP_NAME)
    print(f"Environment: {ENVIRONMENT}")

    try:
        number = randint(1, 10)

        if not is_valid_random_number(number):
            raise ValueError(f"Generated number {number} is out of the expected range.")

        check.display_random_number(number)
        logger.info("Generated valid number: %s", number)

    except (TypeError, ValueError) as error:
        logger.error("Could not generate valid number: %s", error)
        print("Error: Random number generation failed. Please check the logs for details.")

if __name__ == "__main__":
    main()