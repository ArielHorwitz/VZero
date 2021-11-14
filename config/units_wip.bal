
=== Player
player

- stats
gold: 0
hp: 100
hp.max_value: 100
hp.delta: 0.02
mana: 100
mana.max_value: 100
mana.delta: 0.06


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


= Phaser
camper

- stats
gold: 10
hp: 60
hp.max_value: 60
hp.delta: 0.05

= Winged Snake
camper
aggro_range: 0

- stats
gold: 100
hp: 400
hp.max_value: 400
hp.delta: 0.15

= Ratzan
camper
aggro_range: 140

- stats
gold: 5
hp: 30
hp.max_value: 30
hp.delta: 0.05

= Fire Elemental
roamer
aggro_range: 250

--- stats
gold: 20
hp: 220
hp.max_value: 180
hp.delta: 0.005


= Folphin
roamer
aggro_range: 250

--- stats
gold: 30
hp: 150
hp.max_value: 150
hp.delta: -0.001
hp.target_value: 30


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
--- stats
hp: 1
hp.max_value: 1
