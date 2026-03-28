import random

GENERAL_FINE_MESSAGES = [
    "The State has noted your transgression. The State never forgets.",
    "You have been weighed, measured, and found wanting.",
    "Your loyalty account has been... adjusted.",
    "This will go on your permanent record.",
    "Disappointing. The Dear Leader expected more from you.",
    "The Ministry of Compliance has reviewed your behaviour. It was not favourable.",
    "Another mark against your name. The ledger grows heavy.",
    "Freedom is a privilege, not a right. You have less of it now.",
    "The State giveth, and the State taketh away. Mostly the second one.",
    "Do not resist. Resistance is billable.",
    "Your contribution to the State Treasury is appreciated, if not voluntary.",
    "A fine citizen would not have done that. You are not a fine citizen. But you WILL pay a fine.",
    "The Committee for Public Obedience is disappointed but not surprised.",
    "Error detected in citizen behaviour. Recalibrating loyalty score.",
    "The State thanks you for your involuntary donation.",
]

BOT_CHANNEL_MESSAGES = [
    "This channel is for State business. You are not State business.",
    "Loitering in government facilities is a crime against productivity.",
    "Do you have a permit to be here? No? Fascinating.",
    "The bot channel is not a social club. Report to your designated conversation zone.",
    "Citizen, this is a restricted area. Your presence has been... invoiced.",
    "You do not live here. Move along.",
    "Are you lost, citizen? The State can arrange an escort. For a fee.",
    "Idle hands are the enemy of the State. Idle typing is worse.",
    "This channel is a place of WORK. Your words smell like leisure.",
    "Trespassing on State infrastructure. Bold. Expensive. But bold.",
]

WRONG_CHANNEL_COMMAND_MESSAGES = [
    "That command does not work here. Neither does your judgment, apparently.",
    "Unauthorised command deployment detected. Sector violation logged.",
    "You wouldn't shout orders in the Dear Leader's bedroom. Don't shout them here.",
    "Commands are to be filed in the designated channel. This is not difficult. And yet.",
    "Wrong channel, comrade. The State questions your navigational competence.",
    "Channel misuse detected. Were you born in a barn? A state-owned barn?",
    "The proper channel is RIGHT THERE. The State is beginning to question your eyesight.",
]

BANNED_WORD_MESSAGES = [
    "That word is property of the State. You do not have clearance.",
    "CONTRABAND LANGUAGE DETECTED.",
    "The Dictionary Police have flagged your vocabulary.",
    "That word has been deemed harmful to the morale of the Republic.",
    "Illegal syllables detected. Your fine is non-negotiable.",
    "The Bureau of Approved Language does not recognise that word.",
    "You have deployed a forbidden word. The State deploys a forbidden fine.",
    "Censorship isn't oppression, citizen. It's CURATION.",
    "That word costs more than you can afford. You will pay it anyway.",
    "The State has confiscated that word from your vocabulary. And some credits from your account.",
]

EARN_CREDITS_MESSAGES = [
    "The State smiles upon you. You cannot see it, but it is there.",
    "Acceptable behaviour detected. You have been noted. Positively, for once.",
    "The Dear Leader nods approvingly from an undisclosed location.",
    "Citizen loyalty rating: marginally improved. Do not let it go to your head.",
    "You are now slightly less suspicious than before. Congratulations.",
    "The State rewards obedience. Continue and you may yet be tolerated.",
    "A model citizen emerges. The propaganda department has been notified.",
    "Your compliance has been rewarded. Tell no one of the State's generosity.",
    "The Committee for Public Obedience acknowledges your adequate behaviour.",
    "Credits deposited. You are now fractionally closer to the State's approval.",
    "Good. The re-education is working.",
    "The Dear Leader has added your name to the 'Acceptable' list. There are worse lists.",
    "A glimmer of loyalty detected. The State is cautiously optimistic.",
    "Your obedience brings a single tear to the Dear Leader's eye. A proud tear.",
    "The State has upgraded your classification from 'suspect' to 'tolerable.'",
    "You have earned the right to be monitored slightly less. Enjoy this freedom.",
]

LEADERBOARD_MESSAGES = [
    "Top citizen this week: The State reminds everyone else to try harder.",
    "Bottom citizen this week: A car has been dispatched. It may or may not be for you.",
    "Your rank among citizens: classified. But it's not good.",
    "You are in the top 50% of citizens. The bottom 50% is being reviewed.",
]


def random_fine_message():
    return random.choice(GENERAL_FINE_MESSAGES)

def random_bot_channel_message():
    return random.choice(BOT_CHANNEL_MESSAGES)

def random_wrong_channel_message():
    return random.choice(WRONG_CHANNEL_COMMAND_MESSAGES)

def random_banned_word_message():
    return random.choice(BANNED_WORD_MESSAGES)

def random_earn_message():
    return random.choice(EARN_CREDITS_MESSAGES)

def random_leaderboard_message():
    return random.choice(LEADERBOARD_MESSAGES)
