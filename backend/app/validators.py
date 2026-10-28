import re


def is_valid_isin(value: str) -> bool:
    if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value) is None:
        return False

    digits = ""

    for char in value:
        if "A" <= char <= "Z":
            digits += str(ord(char) - ord("A") + 10)
        else:
            digits += char

    total = 0

    for index, char in enumerate(reversed(digits)):
        digit = int(char)

        if index % 2 == 1:
            digit *= 2

        total += digit // 10 + digit % 10

    return total % 10 == 0