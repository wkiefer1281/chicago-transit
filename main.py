# main.py
import pandas as pd
from cta.trains import fetch_train_locations, parse_train_locations

def main():
    xml_data = fetch_train_locations()
    train_df = parse_train_locations(xml_data)
    print(train_df)

if __name__ == "__main__":
    main()
