from joueur.base_ai import BaseAI

from math import sqrt, ceil

# Index definitions for jobs
CORVETTE = 0
MISSILEBOAT = 1
MARTYR = 2
TRANSPORT = 3
MINER = 4

# Unit ratio definitions (in index order)
MAX_UNITS = 20;
NORMAL_RATIOS = [ 0, 0, 0, 1, 1 ] 
NORMAL_RATIOS = [x / sum(NORMAL_RATIOS) for x in NORMAL_RATIOS]

# Miner assignment ratio [ minerals, VP ]
MINER_RATIOS = [ 1, 2 ]
MINER_RATIOS = [x / sum(MINER_RATIOS) for x in MINER_RATIOS]


# Skip logging for competition:
DEBUG = False


def log(fmt='', *args, **kwargs):
    if DEBUG:
        print(fmt.format(*args, **kwargs))

def dist(xa, ya, xb, yb):
    return sqrt((xa - xb) ** 2 + (ya - yb) ** 2)

def distance(a, b):
    return dist(a.x, a.y, b.x, b.y)


def transfer(unit, src, src_distance, go, take, dest, dest_distance, come, give):
    if (
        unit.materials < unit.job.carry_limit
        and (
            distance(unit, src) - src_distance
            < distance(unit, dest) - dest_distance
        )
    ) or unit.materials == 0:
        if go():
            take()
    else:
        if come():
            give()


class AI(BaseAI):
    """ The AI you add and improve code inside to play Stardash. """

    @property
    def game(self):
        """The reference to the Game instance this AI is playing.

        :rtype: games.stardash.game.Game
        """
        return self._game

    @property
    def player(self):
        """The reference to the Player this AI controls in the Game.

        :rtype: games.stardash.player.Player
        """
        return self._player

    def get_name(self):
        """ This is the name you send to the server so your AI will control the
            player named this string.

        Returns
            str: The name of your Player.
        """
        return "btw_i_use_void_now"

    def start(self):
        """ This is called once the game starts and your AI knows its player and
            game. You can initialize your AI here.
        """
        # Debug when playing against self:
        if self.player.name == self.player.opponent.name:
            global DEBUG
            DEBUG = True

        log('----- GAME START -----')
        log('Opponent: {}', self.player.opponent.name)

        self.planet = self.player.home_base
        self.sun = self.game.bodies[2]

        # Calculate asteroid belt geometry
        asteroids = self.game.bodies[3:]
        self.belt_min_radius = min(distance(a, self.sun) for a in asteroids)
        self.belt_max_radius = max(distance(a, self.sun) for a in asteroids)
        self.belt_radius = (self.belt_min_radius + self.belt_max_radius) / 2

        self.unit_ratios = NORMAL_RATIOS

    def job_id(self, job):
        id_map = {
            'corvette': CORVETTE,
            'missileboat': MISSILEBOAT,
            'martyr': MARTYR,
            'transport': TRANSPORT,
            'miner': MINER,
        }
        return id_map[job.title]

    def job_name(self, job_id):
        id_map = {
            CORVETTE: 'corvette',
            MISSILEBOAT: 'missileboat',
            MARTYR: 'martyr',
            TRANSPORT: 'transport',
            MINER: 'miner',
        }

        return id_map[job_id]

    def collides(self, x1, y1, x2, y2):
        length = dist(x1, y1, x2, y2);
        min_dist = self.sun.radius + self.game.ship_radius + 1e-4;

        a = (y1 - y2)
        b = (x2 - x1)
        c = (x1 * y2) - (x2 * y1)
        if a == 0 and b == 0:
            d = float('Inf')
        else:
            d = abs((a * self.sun.x) + (b * self.sun.y) + c) / sqrt((a ** 2) + (b ** 2))

        if d <= min_dist:
            check1 = dist(x1, y1, self.sun.x, self.sun.y) > length
            check2 = dist(x2, y2, self.sun.x, self.sun.y) > length

            if check1 and dist(x2, y2, self.sun.x, self.sun.y) < min_dist:
                return True
            if check2 and dist(x1, y1, self.sun.x, self.sun.y) < min_dist:
                return True
            if not check1 and not check2:
                return True

        return False

    def local_is_dashable(self, unit, x, y):
        return not self.collides(unit.x, unit.y, x, y)

    def local_safe(self, unit, x, y):
        return dist(x, y, self.sun.x, self.sun.y) < self.sun.radius + self.game.ship_radius + 1e-4

    def move_toward(self, unit, target, max_distance=0, energy_cap=0.5):
        target_distance = distance(unit, target)
        #log('unit {} {}', unit.x, unit.y)
        #log('target {} {}', target.x, target.y)
        #log('distance {} -> {}', target_distance, max_distance)
        if target_distance <= max_distance:
            return True

        dest_x = target.x - (target.x - unit.x) * (max_distance - 1e-4) / target_distance
        dest_y = target.y - (target.y - unit.y) * (max_distance - 1e-4) / target_distance

        if target_distance - max_distance > unit.moves:
            if (
                unit.energy - (
                    (target_distance - max_distance)
                    * self.game.dash_cost / self.game.dash_distance
                ) > energy_cap * unit.job.energy
            ):
                assert unit.dash(dest_x, dest_y)
                return False
            else:
                dest_x = unit.x + (
                    (target.x - unit.x) * max(0, unit.moves - 1e-4) / target_distance
                )
                dest_y = unit.y + (
                    (target.y - unit.y) * max(0, unit.moves - 1e-4) / target_distance
                )

        if self.local_safe(unit, dest_x, dest_y):
            assert unit.move(dest_x, dest_y)
        return distance(unit, target) <= max_distance

    def move_safe(self, unit, target, max_distance=0, energy_cap=0.5):
        if self.local_is_dashable(unit, target.x, target.y):
            # Straight line does not cross Sun.
            return self.move_toward(unit, target, max_distance, energy_cap)

        if self.move_toward(unit, self.sun, self.belt_radius, energy_cap):
            assert unit.move(
                unit.x + (
                    (unit.y - self.sun.y) 
                    * max(0, unit.moves - 1e-4) / distance(unit, self.sun)
                ),
                unit.y + (
                    (self.sun.x - unit.x)
                    * max(0, unit.moves - 1e-4) / distance(unit, self.sun)
                ),
            )
        return False

    def game_updated(self):
        """ This is called every time the game's state updates, so if you are
        tracking anything you can update it here.
        """

    def end(self, won, reason):
        """ This is called when the game ends, you can clean up your data and
            dump files here if need be.

        Args:
            won (bool): True means you won, False means you lost.
            reason (str): The human readable string explaining why your AI won
            or lost.
        """
    def run_turn(self):
        """ This is called every time it is this AI.player's turn.

        Returns:
            bool: Represents if you want to end your turn. True means end your
            turn, False means to keep your turn going and re-call this
            function.
        """

        log()
        log('----- BEGIN TURN {} ----', self.game.current_turn)


        # Spawn ships to get close to ratio with the resources available.
        log('Spawning phase')
        log('    Target ratio: {}', self.unit_ratios)
        while len(self.player.units) < MAX_UNITS:
            log('    Money left: {}', self.player.money)
            candidate_jobs = [
                i for i in range(5)
                if self.game.jobs[i].unit_cost < self.player.money
            ]

            log('    Candidates: {}', candidate_jobs)

            if len(candidate_jobs) == 0:
                break

            current_ratios = [0] * 5
            for unit in self.player.units:
                current_ratios[self.job_id(unit.job)] += 1
            current_ratios = [x / sum(current_ratios) for x in current_ratios]
            log('    Current ratio: {}', current_ratios)

            worst_id = candidate_jobs[0]
            worst_diff = self.unit_ratios[worst_id] - current_ratios[worst_id]
            for i in candidate_jobs[1:]:
                diff = self.unit_ratios[i] - current_ratios[i]
                if diff > worst_diff:
                    worst_id = i
                    worst_diff = diff

            log('    Spawning {} ({})', worst_id, self.job_name(worst_id))

            assert self.player.home_base.spawn(
                self.player.home_base.x,
                self.player.home_base.y,
                self.job_name(worst_id),
            )

        units = [[] for _i in range(5)]
        for unit in self.player.units:
            units[self.job_id(unit.job)].append(unit)

        log('Miner phase')

        vp_asteroid = self.game.bodies[3]
        minerals = self.game.bodies[4:]

        miners = units[MINER]
        num_mineral_miners = ceil(MINER_RATIOS[0] * len(miners))

        mineral_miners = miners[:num_mineral_miners]
        vp_miners = miners[num_mineral_miners:]

        mineral_mining = 0
        mineral_transit = 0
        mineral_transfer = 0

        vp_mining = 0
        vp_transit = 0
        vp_transfer = 0

        for miner in mineral_miners:
            def mine():
                in_range = [
                    a for a in minerals
                    if distance(a, miner) <= miner.job.range
                ]
                if in_range:
                    miner.mine(in_range[0])

            transfer(
                miner,
                self.sun,
                self.belt_radius,
                lambda: self.move_toward(miner, self.sun, self.belt_radius),
                lambda: mine(),
                self.planet,
                self.planet.radius,
                lambda: self.move_safe(miner, self.planet, self.planet.radius),
                lambda: None, # Automatic
            )

        for miner in vp_miners:
            if miner.energy > 0.5 * miner.job.energy:
                transfer(
                    miner,
                    vp_asteroid,
                    10,
                    lambda: self.move_safe(miner, vp_asteroid, miner.job.range, 0.4),
                    lambda: miner.mine(vp_asteroid),
                    self.planet,
                    self.planet.radius,
                    lambda: self.move_safe(miner, self.planet, self.planet.radius, 0.4),
                    lambda: None, # Automatic
                )
            else:
                self.move_safe(miner, self.planet, self.planet.radius, 0.1)


        log('    {} mineral miners, {} VP miners', len(mineral_miners), len(vp_miners))

        log('Transport phase')

        transports = units[TRANSPORT]
        # Transports which are farthest from the nearest miner will take precedence
        # to balance the overall distance traveled.
        transports.sort(
            key=lambda t: min(distance(t, m) for m in miners),
            reverse=True,
        )

        miner_assignments = [[m, 0] for m in miners]

        for t in transports:
            target_miner = min(
                miner_assignments,
                key=lambda m: (m[1], distance(t, m[0]))
            )
            target_miner[1] += 1

            def grab():
                for i in reversed(['genarium', 'legendarium', 'rarium', 'mythicite']):
                    if getattr(target_miner[0], i) > 0:
                        t.transfer(target_miner[0], -1, i)

            transfer(
                t,
                target_miner[0],
                10,
                lambda: self.move_safe(t, target_miner[0], 10),
                lambda: grab(),
                self.planet,
                self.planet.radius,
                lambda: self.move_safe(t, self.planet, self.planet.radius),
                lambda: None, # Automatic
            )

        log ('    {} transports', len(transports))

        return True

