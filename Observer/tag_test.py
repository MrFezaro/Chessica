import tag

print("Initializing tag observer...")
tag.init()

while True:
    input("Press Enter to scan board...")
    tag.update_game_state()
    print(tag.game_state)