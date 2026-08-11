def display_random_number(number: int) -> None:
    """Print a generated random number."""
    if not isinstance(number, int):
        raise ValueError("number must be an integer.")
    print(f"Random Number: {number}")