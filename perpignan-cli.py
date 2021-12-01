#!/usr/bin/env python3
import perpignan as p
import sys

class CommandLinePlayer(p.Player):
    helpstr = (
        'c X Y       Place cursor at X Y\n'
        'p? [M S]    Can I place a tile at the current cursor position? And\n'
        '            possibly add M sheeples at slot S?\n'
        'p [M S]     Place a tile at the current cursor position. And possibly\n'
        '            add M sheeples at slot S. Use slot 12 for mill. Using\n'
        '            M=2 adds a regular sheeple; M=3 adds an abbot.\n'
        'r [C]       Rotate tile 90 degrees clockwise C times.\n'
        's           Show game state.\n'
        't           Show next tile data.\n'
        'x           Terminate game.\n'
    )

    def __init__(self, name):
        super().__init__(name)

    def poll_action(self):
        cmd = input(f'{repr(self.name)} ({self.score}p {self.sheeples}sh)> ')
        cmd_parts = cmd.split()
        if len(cmd_parts) == 0:
            cmd_parts = ['']

        try:
            if cmd_parts[0] == 'r':
                turns = 1 if len(cmd_parts) < 2 else int(cmd_parts[1])
                return p.RotateAction(turns)

            elif cmd_parts[0] == 't':
                return p.RequestNextTileAction()
            elif cmd_parts[0] == 's':
                print_perpignan()
            elif cmd_parts[0] == 'c':
                x, y = (int(cmd_parts[1]), int(cmd_parts[2]))
                return p.SetCursorAction(x, y)
            elif cmd_parts[0] in ('p', 'p?'):
                sheeples = 0 if len(cmd_parts) < 2 else int(cmd_parts[1])
                sheeple_slot = 0 if len(cmd_parts) < 3 else int(cmd_parts[2])
                if '?' in cmd_parts[0]:
                    return p.CanPlaceAction(sheeples, sheeple_slot)
                else:
                    return p.PlaceAction(sheeples, sheeple_slot)
            elif cmd_parts[0] == 'x':
                if input('Are you sure you want to quit? [y/n]: ') == 'y':
                    exit() # FIXME
            elif cmd_parts[0] == 'h':
                print(CommandLinePlayer.helpstr)
            else:
                print('Unknown command')
                print(CommandLinePlayer.helpstr)
        except Exception as e:
            print(e)

    def inform(self, msg):
        if type(msg) == p.CanPlaceInfo:
            print('yes' if msg.can_place else f'no; {msg.ynot}')
        elif type(msg) == p.NextTileInfo:
            print(f'{msg.deck_size} cards left; next:\n{msg.tile}')

def print_perpignan():
    grid = perp.board.grid
    cur_x, cur_y = perp.cursor

    # calculate viewport
    def clamp(x):
        return min(max(0, x), len(grid))
    vp_left = clamp(cur_x - 4)
    vp_right = clamp(cur_x + 5)
    vp_top = clamp(cur_y + 4)
    vp_bottom = clamp(cur_y - 3)

    boxtop = '   ' + ('┼' + '─' * 5) * (vp_right - vp_left) + '┼'
    for y in range(vp_top - 1, vp_bottom - 1, -1):
        print(boxtop)
        for i in range(5):
            middle = (i == 2)
            sys.stdout.write(f' {y:2}' if middle else '   ')

            for x in range(vp_left, vp_right):
                sys.stdout.write('│')
                if grid[x][y] is None:
                    if middle and x == cur_x and y == cur_y:
                        sys.stdout.write('  X  ')
                    else:
                        sys.stdout.write('     ')
                else:
                    grid[x][y].print_line(i)
            print('│')
    print(boxtop)

    sys.stdout.write('   ')
    for x in range(vp_left, vp_right):
        sys.stdout.write(f' {x:4} ')
    print()

    if len(perp.deck) > 0:
        print('Next tile:')
        print('\t ┌──012──┐')
        for line in range(5):
            sys.stdout.write('\t')
            isbox = line == 0 or line == 4
            sys.stdout.write(' │ ' if isbox else f'{12 - line:2} ')
            perp.deck[-1].print_line(line)
            sys.stdout.write(' │' if isbox else f' {2 + line}')
            print()
        print('\t └──876──┘')
    else:
        print('Game over.')


perp = p.PerpignanGame()

players = []
while len(players) <= 8:
    name = input(f'Enter player {len(players) + 1} name (leave empty to start playing): ')
    name = name.strip()
    if name == '':
        if len(players) == 0:
            players.append(CommandLinePlayer('player1'))
        break

    if name in (p.name for p in players):
        print('no; player already exists')
    if ' ' in name:
        print('no; space not allowed in name')
    else:
        players.append(CommandLinePlayer(name))

perp.players = players
perp.run()
for player in players:
    print(f'{repr(player.name)}: {player.score}')
