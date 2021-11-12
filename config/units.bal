
=== Player
player

- stats
gold: 0
hp: 100
hp.max_value: 100
hp.delta: 0.02
move_speed: 50
mana: 100
mana.max_value: 100
mana.delta: 0.05
range: 100
damage: 30


=== Blood Imp
camper
aggro_range: 350
deaggro_range: 800
reaggro_range: 100
camp_spread: 50

- stats
gold: 5
hp: 40
hp.max_value: 40
hp.delta: 0.005
move_speed: 45
range: 150
damage: 15
attack_speed: 80


= Phaser
camper

- stats
gold: 10
hp: 60
hp.max_value: 60
hp.delta: 0.05
move_speed: 10
range: 200
damage: 40

= Winged Snake
camper
aggro_range: 0

- stats
gold: 100
hp: 400
hp.max_value: 400
hp.delta: 0.15
move_speed: 10
range: 300
damage: 30
attack_speed: 200

= Ratzan
camper
aggro_range: 140

- stats
gold: 5
hp: 30
hp.max_value: 30
hp.delta: 0.05
move_speed: 80
move_speed.max_value: 200
move_speed.delta: 0.002
range: 100
range.min_value: 50
range.delta: -0.001
damage: 10
attack_speed: 200

= Fire Elemental
roamer
aggro_range: 250

--- stats
gold: 20
hp: 220
hp.max_value: 180
hp.delta: 0.005
move_speed: 70
range: 85
damage: 80


= Folphin
roamer
aggro_range: 250

--- stats
gold: 30
hp: 150
hp.max_value: 150
hp.delta: -0.001
hp.target_value: 30
move_speed: 70
move_speed.max_value: 100
move_speed.delta: 0.1
range: 90
damage: 30
attack_speed: 50
attack_speed.max_value: 200
attack_speed.delta: 0.001


=== Treasure
treasure
--- stats
gold: 250
hp: 300
hp.max_value: 300
hp.delta: 0.5


=== Heros Treasure
treasure
name:Try to pull me out..
--- stats
gold: 1000
hp: 400
hp.max_value: 400
hp.delta: 1.25


=== DPS Meter
dps_meter
---stats
hp: 1
hp.max_value: 1
