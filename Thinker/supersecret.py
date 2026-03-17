import random

def makeThing() -> str:
    things = [
        "owie thinky",
        "done when?",
        "t h i n k i n g",
        "thinky",
        "wah",
        "a-",
        "thinky " * random.randint(1, 5),
        "removing enemy king! ...wait no",
        "BRIBING ENEMY PLAYER WITH CHOCOLATE IN PROGRESS...",
        "choice hard",
        "did I win?",
        "noting down",
        "making a move",
        "moving a make",
        "baking a cake",
        "caking a bake",
        "*crunchy noises*",
        "*chewing noises*",
        "*computer noises*",
        "RETICULATING SPLINES",
        "Downloading more RAM...",
        "Asserting fluctuations in the NFT market for optimal purchase 10 years in advance...",
        "I got your IP address: 127.0.0.1 >:)",
        "throwing a die",
        "throwing bones",
        "pondering the orb",
        "Performing most optimal O(n!) devandergaussing calcuations...",
        "It seems like you are trying to play the game. Want me to make a move for you?",
    ]
    result = random.choice(things)
    
    return result