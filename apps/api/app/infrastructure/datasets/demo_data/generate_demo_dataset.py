"""Generate the built-in demo dataset (edi_demo.jsonl).

Every answer is computed from its question, so the rows are correct by construction and
share one response style ("answer, then working") that fine-tuning can visibly learn.
Run from this directory: python generate_demo_dataset.py
"""

import json
import math
import random
from pathlib import Path

CAPITALS = [
    ("France", "Paris"),
    ("Germany", "Berlin"),
    ("Italy", "Rome"),
    ("Spain", "Madrid"),
    ("Japan", "Tokyo"),
    ("India", "New Delhi"),
    ("China", "Beijing"),
    ("Canada", "Ottawa"),
    ("Australia", "Canberra"),
    ("Brazil", "Brasília"),
    ("Egypt", "Cairo"),
    ("Kenya", "Nairobi"),
    ("Russia", "Moscow"),
    ("the United Kingdom", "London"),
    ("Portugal", "Lisbon"),
    ("Greece", "Athens"),
    ("Norway", "Oslo"),
    ("Sweden", "Stockholm"),
    ("Finland", "Helsinki"),
    ("Denmark", "Copenhagen"),
    ("Poland", "Warsaw"),
    ("Austria", "Vienna"),
    ("Ireland", "Dublin"),
    ("Mexico", "Mexico City"),
    ("Argentina", "Buenos Aires"),
    ("Nepal", "Kathmandu"),
    ("Bangladesh", "Dhaka"),
    ("Thailand", "Bangkok"),
    ("Vietnam", "Hanoi"),
    ("South Korea", "Seoul"),
    ("Turkey", "Ankara"),
    ("Saudi Arabia", "Riyadh"),
]

UNIT_CONVERSIONS = [
    ("kilometres", "metres", 1000),
    ("metres", "centimetres", 100),
    ("kilograms", "grams", 1000),
    ("hours", "minutes", 60),
    ("minutes", "seconds", 60),
    ("litres", "millilitres", 1000),
]


def fmt(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text != "-0" else "0"


def ohms_law_voltage(rng: random.Random) -> tuple[str, str]:
    resistance = rng.choice(range(10, 1001, 10))
    current = rng.choice(range(1, 51)) / 10
    voltage = current * resistance
    return (
        (f"A resistor of {resistance} ohms carries a current of {fmt(current)} A. "
        "What is the voltage across it?"),
        (f"The voltage across the resistor is {fmt(voltage)} V.\n\n"
        f"Working: Ohm's law gives V = I × R = {fmt(current)} A × {resistance} Ω = {fmt(voltage)} V."),
    )


def ohms_law_current(rng: random.Random) -> tuple[str, str]:
    resistance = rng.choice(range(10, 1001, 10))
    voltage = rng.choice(range(1, 241))
    current = voltage / resistance
    return (
        (f"A {voltage} V supply is connected across a {resistance} ohm resistor. "
        "What current flows through it?"),
        (f"The current is {fmt(round(current, 4))} A.\n\n"
        f"Working: Ohm's law gives I = V ÷ R = {voltage} V ÷ {resistance} Ω ≈ {fmt(round(current, 4))} A."),
    )


def electrical_power(rng: random.Random) -> tuple[str, str]:
    voltage = rng.choice([5, 9, 12, 24, 48, 110, 230])
    current = rng.choice(range(1, 101)) / 10
    power = voltage * current
    return (
        f"A device runs at {voltage} V and draws {fmt(current)} A. How much power does it use?",
        (f"The device uses {fmt(power)} W.\n\n"
        f"Working: P = V × I = {voltage} V × {fmt(current)} A = {fmt(power)} W."),
    )


def unit_conversion(rng: random.Random) -> tuple[str, str]:
    source, target, factor = rng.choice(UNIT_CONVERSIONS)
    amount = rng.choice(range(1, 200)) / rng.choice([1, 2, 4])
    converted = amount * factor
    return (
        f"Convert {fmt(amount)} {source} to {target}.",
        (f"{fmt(amount)} {source} is {fmt(converted)} {target}.\n\n"
        f"Working: there are {factor} {target} in one {source[:-1]}, so {fmt(amount)} × {factor} = {fmt(converted)}."),
    )


def celsius_to_fahrenheit(rng: random.Random) -> tuple[str, str]:
    celsius = rng.choice(range(-40, 121))
    fahrenheit = celsius * 9 / 5 + 32
    return (
        f"Convert {celsius} °C to Fahrenheit.",
        (f"{celsius} °C is {fmt(fahrenheit)} °F.\n\n"
        f"Working: °F = °C × 9/5 + 32 = {celsius} × 9/5 + 32 = {fmt(fahrenheit)}."),
    )


def binary_conversion(rng: random.Random) -> tuple[str, str]:
    number = rng.choice(range(2, 1024))
    return (
        f"Convert the decimal number {number} to binary.",
        (f"{number} in binary is {number:b}.\n\n"
        f"Working: repeatedly dividing {number} by 2 and reading the remainders from last to first gives {number:b}."),
    )


def hex_conversion(rng: random.Random) -> tuple[str, str]:
    number = rng.choice(range(16, 4096))
    return (
        f"Convert the decimal number {number} to hexadecimal.",
        (f"{number} in hexadecimal is {number:X}.\n\n"
        f"Working: repeatedly dividing {number} by 16 and reading the remainders from last to first gives {number:X}."),
    )


def circle_area(rng: random.Random) -> tuple[str, str]:
    radius = rng.choice(range(1, 151))
    area = round(math.pi * radius * radius, 2)
    return (
        f"What is the area of a circle with a radius of {radius} cm?",
        (f"The area is about {fmt(area)} cm².\n\n"
        f"Working: A = π × r² = π × {radius}² ≈ {fmt(area)} cm²."),
    )


def percentage(rng: random.Random) -> tuple[str, str]:
    percent = rng.choice([5, 10, 12, 15, 20, 25, 30, 40, 50, 75])
    amount = rng.choice(range(20, 2001, 20))
    result = percent * amount / 100
    return (
        f"What is {percent}% of {amount}?",
        (f"{percent}% of {amount} is {fmt(result)}.\n\n"
        f"Working: {percent}% × {amount} = {percent}/100 × {amount} = {fmt(result)}."),
    )


GENERATORS = [
    ohms_law_voltage,
    ohms_law_current,
    electrical_power,
    unit_conversion,
    celsius_to_fahrenheit,
    binary_conversion,
    hex_conversion,
    circle_area,
    percentage,
]


def build_rows(rows_per_generator: int = 55, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    seen: set[str] = set()
    rows: list[dict] = []
    for generator in GENERATORS:
        produced = 0
        attempts = 0
        while produced < rows_per_generator:
            attempts += 1
            if attempts > rows_per_generator * 50:
                raise RuntimeError(f"{generator.__name__} cannot produce {rows_per_generator} unique rows.")
            instruction, output = generator(rng)
            if instruction in seen:
                continue
            seen.add(instruction)
            rows.append({"instruction": instruction, "output": output})
            produced += 1
    for country, capital in CAPITALS:
        rows.append(
            {
                "instruction": f"What is the capital of {country}?",
                "output": f"The capital of {country} is {capital}.\n\n"
                f"Working: this is a geography fact; {capital} is the seat of {country}'s national government.",
            }
        )
    rng.shuffle(rows)
    return rows


if __name__ == "__main__":
    destination = Path(__file__).with_name("edi_demo.jsonl")
    with destination.open("w", encoding="utf-8", newline="\n") as file:
        for row in build_rows():
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {destination}")
