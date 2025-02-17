from enum import Enum

class Route(Enum):
    """Enum of the different train lines.

    Codes found in the API documentation.

    """

    RED = "red"
    BLUE = "blue"
    BROWN = "brn"
    GREEN = "g"
    ORANGE = "org"
    PURPLE = "p"
    PINK = "pink"
    YELLOW = "y"

class RouteName:
    
    def __init__(self):
        self.route_names = {
            "red": "Red",
            "blue": "Blue",
            "brn": "Brown",
            "g": "Green",
            "org": "Orange",
            "p": "Purple",
            "pink": "Pink",
            "y": "Yellow"
        }

    def get_route_name(self, key):
        return self.route_names.get(key, 'Unknown')