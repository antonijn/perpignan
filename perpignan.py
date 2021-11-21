from PIL import Image, ImageFilter
import json
import os.path
import random
import sys

class Slot:
    def __init__(self):
        self.feature = None

class TileSlot(Slot):
    def __init__(self, tile):
        super().__init__()
        self.tile = tile

class EdgeSlot(TileSlot):
    def __init__(self, tile):
        super().__init__(tile)
        self.available = True

class Feature:
    def __init__(self):
        self.slots = []
        self.player_sheeples = {}
        self.completed = False

    def plugin(self, slot):
        slot.feature = self
        self.slots.append(slot)

    def absorb(self, other, perpignan):
        if self is other:
            return

        for p in other.player_sheeples:
            if p not in self.player_sheeples:
                self.player_sheeples[p] = 0

            self.player_sheeples[p] += other.player_sheeples[p]

        for s in other.slots:
            s.feature = self

        self.slots.extend(other.slots)

        other.slots = []
        other.player_sheeples = {}

        if self.should_complete():
            self.complete(perpignan)

    def tiles(self):
        unique_tiles = {}
        for slot in self.slots:
            if isinstance(slot, TileSlot):
                unique_tiles[slot.tile] = True

        return (tile for tile in unique_tiles)

    def score(self, endgame=False):
        raise NotImplementedError()

    def complete(self, perpignan, endgame=False):
        if self.completed:
            return

        score = self.score(endgame=endgame)
        most_sheeples = max(self.player_sheeples.values(), default=-1)

        self.completed = True

        for p in self.player_sheeples:
            sheeples = self.player_sheeples[p]
            p.sheeples += sheeples
            perpignan.log(PlayerSheepleInfo(p))
            if sheeples == most_sheeples:
                p.score += score
                perpignan.log(PlayerScoreInfo(p))

        perpignan.log(CompletedInfo(self))

    def should_complete(self):
        return False

    def to_dict(self):
        perimeter = []
        for tile in self.tiles():
            tslots = [i for i in range(len(tile.slots)) if tile.slots[i].feature is self]
            perimeter.append({'x': tile.x, 'y': tile.y, 'slots': tslots})

        return {
            'type': type(self).__name__,
            'perimeter': perimeter
        }

class Town(Feature):
    def __init__(self):
        super().__init__()

    def score(self, endgame=False):
        tiles = {}
        for s in self.slots:
            if isinstance(s, EdgeSlot):
                tiles[s.tile] = True
        return len(tiles) * (1 if endgame else 2)

    def should_complete(self):
        for s in self.slots:
            if isinstance(s, EdgeSlot) and s.available:
                return False

        return True

class Road(Feature):
    def __init__(self):
        super().__init__()
        self.completed = False

    def score(self, endgame=False):
        tiles = {}
        for s in self.slots:
            if isinstance(s, EdgeSlot):
                tiles[s.tile] = True
        return len(tiles)

    def should_complete(self):
        for s in self.slots:
            if isinstance(s, EdgeSlot) and s.available:
                return False

        return True

class Meadow(Feature):
    def __init__(self):
        super().__init__()
        self.town_slots = []

    def score(self, endgame=False):
        towns = {}
        for s in self.town_slots:
            if s.feature.completed:
                towns[s.feature] = True
        return len(towns) * 3

    def absorb(self, other, perpignan):
        super().absorb(other, perpignan)
        if self is other:
            return

        self.town_slots.extend(other.town_slots)
        other.town_slots = []

class Mill(Feature):
    def __init__(self):
        super().__init__()

    def should_complete(self):
        return self.slots[0].tile.neighbours == 8

    def score(self, endgame=False):
        return self.slots[0].tile.neighbours + 1

def pixels_equal(pix1, pix2):
    return pix1 == pix2

def pixels_connected(image, pos_a, pos_b, compare=pixels_equal):
    # -1 unsearched, 0 not connected, 1 connected
    imwidth, imheight = image.size
    state = [[-1] * imwidth for _ in range(imheight)]
    pix_a = image.getpixel(pos_a)

    def depth_first(pos):
        if pos == pos_b:
            return True

        poss_nxbours = [
            (pos[0] - 1, pos[1]),
            (pos[0] + 1, pos[1]),
            (pos[0], pos[1] - 1),
            (pos[0], pos[1] + 1),
        ]
        nxbours = [
            nx for nx in poss_nxbours
            if  nx[0] >= 0 and nx[0] < imwidth
            and nx[1] >= 0 and nx[1] < imheight
            and state[nx[0]][nx[1]] == -1
        ]

        for nx in nxbours:
            pix_b = image.getpixel(nx)
            state[nx[0]][nx[1]] = 1 if compare(pix_a, pix_b) else 0

        for nx in nxbours:
            if state[nx[0]][nx[1]] == 1 and depth_first(nx):
                return True

        return False

    return depth_first(pos_a)


class Tile:
    slot_offsets = {
        ( 0,  1): 0,
        ( 1,  0): 3,
        ( 0, -1): 6,
        (-1,  0): 9,
    }

    def __init__(self):
        self.slots = [EdgeSlot(self) for _ in range(3 * 4)]
        # the slot for the mill
        self.slots.append(TileSlot(self))
        self.x = -1
        self.y = -1
        self.neighbours = 0

    def add_neighbours(self, nx, perpignan):
        self.neighbours += nx
        if self.neighbours == 8 and isinstance(self.slots[12].feature, Mill):
            self.slots[12].feature.complete(perpignan)

    def rotate_cw(self):
        mill_slot = self.slots[12]
        self.slots = [self.slots[(i + 9) % 12] for i in range(3 * 4)]
        self.slots.append(mill_slot)

    def rotate_ccw(self):
        mill_slot = self.slots[12]
        self.slots = [self.slots[(i + 3) % 12] for i in range(3 * 4)]
        self.slots.append(mill_slot)

    def features(self):
        feats = {}
        for s in self.slots:
            if s.feature is not None:
                feats[s.feature] = True
        return (feat for feat in feats)

    def __str__(self):
        feat_slots = {}
        for i in range(len(self.slots)):
            slot = self.slots[i]
            feat = slot.feature
            if feat is None:
                continue
            if feat not in feat_slots:
                feat_slots[feat] = []
            feat_slots[feat].append(i)
                
        featstr = '\n'.join(
            f'\t{type(feat).__name__} {feat_slots[feat]}'
            for feat in feat_slots
        )
        return featstr + '\n'

    def to_dict(self):
        feat_slots = {}
        for i in range(len(self.slots)):
            slot = self.slots[i]
            feat = slot.feature
            if feat is None:
                continue
            if feat not in feat_slots:
                feat_slots[feat] = []
            feat_slots[feat].append(i)

        feats = []
        for feat in feat_slots:
            feats.append({'type': type(feat).__name__, 'slots': feat_slots[feat]})

        return {'type': 'Tile', 'features': feats}

    def print_line(self, line):
        which_slots = {
            0: [-1,  0,  1,  2, -1],
            1: [11, -1,  1, -1,  3],
            2: [10, 10, 12,  4,  4],
            3: [ 9, -1,  7, -1,  5],
            4: [-1,  8,  7,  6, -1],
        }
        symbols = { Town: 'o', Road: '+', Meadow: '.', type(None): 'w', Mill: '$' }

        if line not in which_slots:
            return

        for i in which_slots[line]:
            if i == -1:
                sys.stdout.write(' ')
                continue

            sys.stdout.write(symbols[type(self.slots[i].feature)])

    def print(self):
        for i in range(5):
            self.print_line(i)
            print()

    @staticmethod
    def from_bitmap(image):
        tile = Tile()

        pixels = [
            (1, 0), (2, 0), (3, 0),
            (4, 1), (4, 2), (4, 3),
            (3, 4), (2, 4), (1, 4),
            (0, 3), (0, 2), (0, 1),
        ]

        constructors = {
            (255,   0,   0): lambda : Road(),
            (  0, 255,   0): lambda : Meadow(),
            (255,   1,   0): lambda : Meadow(), # Hacky shit for tile 24
            (  0,   0, 255): lambda : Town(),
        }

        visited = {}
        features = []
        for i in range(12):
            if i in visited:
                continue

            pix = image.getpixel(pixels[i])

            if pix not in constructors:
                continue

            feat = constructors[pix]()
            feat.plugin(tile.slots[i])
            features.append(feat)

            for j in range(i + 1, 12):
                if j in visited:
                    continue

                # Hacky shit again, allow for one pixel difference for
                # tile 24
                def cmp(pix_a, pix_b):
                    a, b, c = pix_a
                    x, y, z = pix_b
                    return (abs(a - x) + abs(b - y) + abs(c - z)) <= 1

                if pixels_connected(image, pixels[i], pixels[j], cmp):
                    feat.plugin(tile.slots[j])
                    visited[j] = True

        if image.getpixel((2, 2)) == (255, 255, 255):
            feat = Mill()
            feat.plugin(tile.slots[12])

        # connect the towns to the meadows, so they can be scored in
        # the end
        meadow_towns = [
            (m, t)
            for m in features
            for t in features
            if  type(m) == Meadow
            and type(t) == Town
        ]

        gb = [(0, 255, 0), (0, 0, 255)]
        def green_or_blue(pix_a, pix_b):
            return pix_a in gb and pix_b in gb

        for m, t in meadow_towns:
            idx_m = tile.slots.index(m.slots[0])
            idx_t = tile.slots.index(t.slots[0])
            connected = pixels_connected(image, pixels[idx_m], pixels[idx_t], green_or_blue)
            if connected:
                s = Slot()
                m.town_slots.append(s)
                t.plugin(s)

        return tile

    @staticmethod
    def deck_from_bitmap(im, w=7, h=12, res=5):
        return [
            Tile.from_bitmap(im.crop((x * res, y * res, (x + 1) * res, (y + 1) * res)))
            for y in range(h) for x in range(w)
        ]

class CantPlaceThatThereError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason

class PlayerAction:
    pass

class SetCursorAction(PlayerAction):
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

class RotateAction(PlayerAction):
    def __init__(self, turns: int):
        if abs(turns) >= 4:
            raise ValueError('too many turns')
        self.turns = turns

class CanPlaceAction(PlayerAction):
    def __init__(self, sheeples: int, sheeple_slot: int):
        if sheeples not in (0, 2, 3):
            raise ValueError('invalid number of sheeples')
        if sheeple_slot < 0 or sheeple_slot > 12:
            raise ValueError('invalid sheeple slot')

        self.sheeples = sheeples
        self.sheeple_slot = sheeple_slot

class PlaceAction(CanPlaceAction):
    def __init__(self, sheeples: int, sheeple_slot: int):
        super().__init__(sheeples, sheeple_slot)

class PlayerQuitAction(PlayerAction):
    pass

class RequestNextTileAction(PlayerAction):
    pass

class StateChangeInfo:
    def to_dict(self):
        raise NotImplementedError()

class NextTurnInfo(StateChangeInfo):
    def __init__(self, player):
        self.player = player

    def to_dict(self):
        return {
            'type': type(self).__name__,
            'player': self.player.name
        }

class PlayerScoreInfo(StateChangeInfo):
    def __init__(self, player):
        self.player = player

    def to_dict(self):
        return {
            'type': type(self).__name__,
            'player': self.player.name,
            'score': self.player.score
        }

class PlayerSheepleInfo(StateChangeInfo):
    def __init__(self, player):
        self.player = player

    def to_dict(self):
        return {
            'type': type(self).__name__,
            'player': self.player.name,
            'sheeples': self.player.sheeples
        }

class PlayerQuitInfo(StateChangeInfo):
    def __init__(self, player):
        self.player = player

    def to_dict(self):
        return {
            'type': type(self).__name__,
            'player': self.player.name
        }

class TilePlaceInfo(StateChangeInfo):
    def __init__(self, tile, sheeples: int, sheeple_slot: int):
        self.tile = tile
        self.sheeples = sheeples
        self.sheeple_slot = sheeple_slot

    def to_dict(self):
        d = {
            'type': type(self).__name__,
            'tile': self.tile.to_dict(),
            'x': self.tile.x,
            'y': self.tile.y
        }
        if self.sheeples > 0:
            d['sheeples'] = self.sheeples
            d['sheeple_slot'] = self.sheeple_slot
        return d

class CompletedInfo(StateChangeInfo):
    def __init__(self, feature):
        self.feature = feature

    def to_dict(self):
        return {
            'type': type(self).__name__,
            'feature': self.feature.to_dict()
        }

class UserErrorInfo(StateChangeInfo):
    def __init__(self, msg):
        self.msg = msg

    def to_dict(self):
        return {
            'type': type(self).__name__,
            'msg': msg
        }

class ResponseInfo(StateChangeInfo):
    pass

class CanPlaceInfo(ResponseInfo):
    def __init__(self, can_place: bool, ynot: str):
        self.can_place = can_place
        self.ynot = ynot

    def to_dict(self):
        return {
            'type': type(self).__name__,
            'can_place': self.can_place,
            'ynot': self.ynot
        }

class NextTileInfo(ResponseInfo):
    def __init__(self, tile, deck_size: int):
        self.tile = tile
        self.deck_size = deck_size

    def to_dict(self):
        return {
            'type': type(self).__name__,
            'tile': self.tile.to_dict(),
            'deck_size': self.deck_size
        }

class Perpignan:
    def __init__(self):
        self.grid = [[None for y in range(7 * 12)] for x in range(7 * 12)]

        bmp_path = os.path.join(os.path.dirname(__file__), 'tiles.png')
        deck = Tile.deck_from_bitmap(Image.open(bmp_path))
        deck1 = deck[:14]
        deck2 = deck[15:]
        start_tile = deck[14]
        self.grid[42][42] = start_tile
        start_tile.x = 42
        start_tile.y = 42
        deck = deck1 + deck2
        random.shuffle(deck)
        self.deck = deck

        self.available = {(43, 42): True, (42, 43): True, (41, 42): True, (42, 41): True}
        self.cursor = (43, 42)
        self.players = []
        self.active_player = None
        self.active_player_idx = -1

    def run(self):
        if len(self.players) == 0:
            return

        self.log(TilePlaceInfo(self.grid[42][42], 0, 0))

        self.next_player()
        while len(self.deck) > 0:
            self.log(NextTurnInfo(self.active_player))

            act = self.active_player.poll_action()
            try:
                self.handle_action(act)
            except Exception as e:
                print(e)

        self.end_game()

    def handle_action(self, act):
        if type(act) == SetCursorAction:
            self.cursor = (act.x, act.y)

        elif type(act) == RotateAction:
            tile = self.deck[-1]
            rotation = tile.rotate_cw if act.turns > 0 else tile.rotate_ccw
            for _ in range(abs(act.turns)):
                rotation()

        elif type(act) == PlaceAction:
            self.place(sheeples=act.sheeples, sheeple_slot=act.sheeple_slot)

        elif type(act) == RequestNextTileAction:
            self.active_player.inform(NextTileInfo(self.deck[-1], len(self.deck)))

        elif type(act) == CanPlaceAction:
            can, ynot = self.can_place_and_ynot(sheeples=act.sheeples, sheeple_slot=act.sheeple_slot)
            self.active_player.inform(CanPlaceInfo(can, ynot))

        elif type(act) == PlayerQuitAction:
            del self.players[self.active_player_idx]

    def next_player(self):
        self.active_player_idx = (self.active_player_idx + 1) % len(self.players)
        self.active_player = self.players[self.active_player_idx]

    def log(self, msg):
        for p in self.players:
            p.inform(msg)

    def inbounds(self, x, y):
        return x >= 0 and x < len(self.grid) and y >= 0 and y < len(self.grid)

    def can_place(self, sheeple_slot=0, sheeples=0) -> bool:
        can, ynot = self.can_place_and_ynot(sheeple_slot, sheeples)
        return can

    def can_place_and_ynot(self, sheeple_slot=0, sheeples=0) -> (bool, str):
        try:
            self.place(sheeple_slot, sheeples, commit=False)
        except CantPlaceThatThereError as e:
            return False, e.reason
        return True, None

    def place(self, sheeple_slot=0, sheeples=0, commit=True):
        """
        Place the current tile on the board.

        :param Player player: The player who is doing the placing.
        :param sheeple_slot: At which slot to place a sheeple.
        :type sheeple_slot: integer or None
        :param int sheeples: How many sheeples to place.
        :param bool commit: Whether to actually perform the placement,
                            or just do a try run.
        :raises ValueError: if sheeple_slot is not in the range 0-12,
                            or sheeples is not in the range 0,2-3.
        :raises CantPlaceThatThereError: if placement violates the rules.
        """
        if len(self.deck) == 0:
            raise CantPlaceThatThereError('no tiles')

        tile = self.deck[-1]
        x, y = self.cursor

        if not self.inbounds(x, y):
            raise CantPlaceThatThereError('out of bounds')

        if self.grid[x][y] is not None:
            raise CantPlaceThatThereError('occupied')

        if sheeples != 0:
            if sheeple_slot < 0 or sheeple_slot > 12:
                raise ValueError('invalid slot')
            if sheeples not in (2, 3):
                raise ValueError('invalid number of sheeples')
            if tile.slots[sheeple_slot].feature is None:
                raise CantPlaceThatThereError(f'sheeple on river at {sheeple_slot}')
            if sheeple_slot == 12 and not isinstance(tile.slots[12].feature, Mill):
                raise CantPlaceThatThereError('tile has no mill')
            if self.active_player.sheeples < sheeples:
                raise CantPlaceThatThereError('not enough sheeples')
            if sheeples == 3 and (self.active_player.sheeples % 2) != 1:
                raise CantPlaceThatThereError('abbot already in use')
            if sheeples == 2 and self.active_player.sheeples == 3:
                raise CantPlaceThatThereError('only abbot left')

        nxbours = []
        # where you can place a tile after this one has been placed
        becomes_available = []
        for (dx, dy) in Tile.slot_offsets:
            x_b = x + dx
            y_b = y + dy
            if not self.inbounds(x_b, y_b):
                continue

            tile_b = self.grid[x_b][y_b]

            if tile_b is None:
                becomes_available.append((x_b, y_b))
                continue

            nxbours.append((tile_b, (dx, dy)))

        if len(nxbours) == 0:
            raise CantPlaceThatThereError('in void')

        # find out if all features match
        for tile_b, (dx, dy) in nxbours:
            offset = Tile.slot_offsets[(dx, dy)]
            offset_b = Tile.slot_offsets[(-dx, -dy)]

            for i in range(3):
                idx = offset + i
                idx_b = offset_b + 2 - i
                feat = tile.slots[idx].feature
                feat_b = tile_b.slots[idx_b].feature
                if type(feat) is not type(feat_b):
                    raise CantPlaceThatThereError(f'mismatch at {idx}')

                if sheeples > 0 and sheeple_slot == idx:
                    if feat_b is not None and len(feat_b.player_sheeples) > 0:
                        raise CantPlaceThatThereError('sheeple conflict')

        if not commit:
            return

        self.grid[x][y] = tile
        tile.x = x
        tile.y = y
        del self.available[(x, y)]
        for coord in becomes_available:
            self.available[coord] = True

        if sheeples > 0:
            tile.slots[sheeple_slot].feature.player_sheeples[self.active_player] = sheeples
            self.active_player.sheeples -= sheeples
            self.log(PlayerSheepleInfo(self.active_player))

        self.log(TilePlaceInfo(tile, sheeples, sheeple_slot))

        # mark connected edge slots as unavailable
        for tile_b, (dx, dy) in nxbours:
            offset = Tile.slot_offsets[(dx, dy)]
            offset_b = Tile.slot_offsets[(-dx, -dy)]
            for i in range(3):
                slot = tile.slots[offset + i]
                slot.available = False
                slot_b = tile_b.slots[offset_b + 2 - i]
                slot_b.available = False

        # merge features into existing game
        for tile_b, (dx, dy) in nxbours:
            offset = Tile.slot_offsets[(dx, dy)]
            offset_b = Tile.slot_offsets[(-dx, -dy)]
            for i in range(3):
                feat = tile.slots[offset + i].feature
                feat_b = tile_b.slots[offset_b + 2 - i].feature
                if feat_b is not None:
                    feat_b.absorb(feat, self)

        # update to complete any neighbouring mills
        all_neighbours = [
            self.grid[x + i][y + j]
            for i in (-1, 0, 1)
            for j in (-1, 0, 1)
            if  (i != 0 or j != 0)
            and self.inbounds(x + i, y + j)
            and self.grid[x + i][y + j] is not None
        ]

        tile.add_neighbours(len(all_neighbours), self)
        for nx in all_neighbours:
            nx.add_neighbours(1, self)

        # we're done with this tile, and current player's turn has ended
        self.deck.pop()
        self.next_player()

        # see if the new tile fits anywhere; draw a new one if not
        nofit = []
        while len(self.deck) > 0 and not self.new_tile_fits_anywhere():
            nofit.append(self.deck.pop())

        # if nothing fits (i.e. len(self.deck) == 0), then we leave the
        # deck empty to terminate the game
        if len(self.deck) > 0 and len(nofit) > 0:
            tile_that_fits = self.deck.pop()
            deck = self.deck + nofit
            random.shuffle(deck)
            deck.append(tile_that_fits)
            self.deck = deck

    def new_tile_fits_anywhere(self):
        if len(self.deck) == 0:
            return False

        cur = self.cursor
        try:
            new_tile = self.deck[-1]
            for (x, y) in self.available:
                self.cursor = (x, y)
                fits = False
                for _ in range(4):
                    new_tile.rotate_cw()
                    # we don't return just yet even if it fits; let's
                    # restore the tile's original orientation first
                    fits = fits or self.can_place()
                if fits:
                    return True

            return False
        finally:
            self.cursor = cur

    def end_game(self):
        features = (
            s.feature
            for tiles in self.grid
            for tile in tiles
            if tile is not None
            for s in tile.slots
            if s.feature is not None
        )

        unique_features = {}
        for feat in features:
            unique_features[feat] = True

        for feat in unique_features:
            feat.complete(self, endgame=True)

class Player:
    def __init__(self, name):
        self.score = 0
        self.sheeples = 19
        self.name = name

    def poll_action(self):
        raise NotImplementedError()

    def inform(self, msg):
        raise NotImplementedError()
