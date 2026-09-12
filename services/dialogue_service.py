"""
Mnemonic Dialogue Service for TelegramDevBridge.
Provides multi-scenario, contextually relevant dialogues for EVERY topic:
TAXI, HOTEL, RESTAURANT, AIRPORT, SHOPPING, DOCTOR, BANK, COMBO.
Strictly maintains topic continuity until intentionally changed by the user.
"""

from typing import List, Dict, Any, Optional

# Canonical topic normalizer
TOPIC_ALIASES = {
    "taxi": "taxi",
    "taksi": "taxi",
    "cab": "taxi",
    "hotel": "hotel",
    "mehmonxona": "hotel",
    "motel": "hotel",
    "inn": "hotel",
    "restaurant": "restaurant",
    "restoran": "restaurant",
    "cafe": "restaurant",
    "kafe": "restaurant",
    "qahva": "restaurant",
    "dining": "restaurant",
    "airport": "airport",
    "aeroport": "airport",
    "travel": "airport",
    "sayohat": "airport",
    "flight": "airport",
    "shopping": "shopping",
    "xarid": "shopping",
    "market": "shopping",
    "bozor": "shopping",
    "dokon": "shopping",
    "mall": "shopping",
    "doctor": "doctor",
    "shifokor": "doctor",
    "pharmacy": "doctor",
    "dorixona": "doctor",
    "dori": "doctor",
    "clinic": "doctor",
    "hospital": "doctor",
    "bank": "bank",
    "moliya": "bank",
    "finance": "bank",
    "atm": "bank",
    "combo": "combo",
    "birlashgan": "combo",
}

TOPIC_METADATA = {
    "taxi": {"name": "Taksi (Taxi)", "icon": "🚕", "desc": "Shahar taksisi, ilova orqali chaqirish, yo'l haqi to'lash"},
    "hotel": {"name": "Mehmonxona (Hotel)", "icon": "🏨", "desc": "Xonani bron qilish, ro'yxatdan o'tish, xizmat ko'rsatish"},
    "restaurant": {"name": "Restoran (Restaurant)", "icon": "🍽️", "desc": "Stol band qilish, menyudan taom tanlash, hisob-kitob"},
    "airport": {"name": "Aeroport (Airport)", "icon": "✈️", "desc": "Chipta ro'yxatdan o'tkazish, bagaj, parvozga chiqish"},
    "shopping": {"name": "Xarid (Shopping)", "icon": "🛍️", "desc": "Kiyim va oziq-ovqat xaridi, o'lcham almashtirish, chegirma"},
    "doctor": {"name": "Shifokor (Doctor)", "icon": "🏥", "desc": "Klinikada qabul, simptomlar, dorixonadan dori olish"},
    "bank": {"name": "Bank (Bank)", "icon": "🏦", "desc": "Hisob ochish, valyuta ayirboshlash, karta xavfsizligi"},
    "combo": {"name": "Combo (Birlashgan)", "icon": "🌟", "desc": "Shahar bo'ylab kompleks hayotiy vaziyatlar zanjiri"},
}


def normalize_topic(raw_topic: Optional[str]) -> str:
    """Mavzu nomini rasmiy identifikatorga aylantiradi."""
    if not raw_topic:
        return "taxi"
    clean = str(raw_topic).lower().strip()
    for alias, canonical in TOPIC_ALIASES.items():
        if alias in clean:
            return canonical
    return "taxi"


# Pre-authored realistic dialogue scenarios
DIALOGUES_DB: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "en": {
        "taxi": [
            {
                "id": "en_taxi_0",
                "title": "Hailing a City Taxi (Vokzalga shoshilinch borish)",
                "situationUz": "Yo'lovchi shoshilinch ravishda vokzalga yetib olish uchun taksi to'xtatmoqda.",
                "targetWords": ["Station", "Shortcut", "Traffic", "Seatbelt", "Receipt"],
                "lines": [
                    {"speaker": "Passenger", "speakerIcon": "👨", "textTarget": "Good morning! Are you available? I need to get to the Central Station quickly.", "textUz": "Xayrli tong! Bo'shmisiz? Men zudlik bilan Markaziy Vokzalga borishim kerak."},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "Hello! Yes, hop in. There is some morning traffic, but I know a quick shortcut.", "textUz": "Salom! Ha, chiqing. Ertalab tirbandlik bor, lekin qisqa yo'lni bilaman."},
                    {"speaker": "Passenger", "speakerIcon": "👨", "textTarget": "That is wonderful! How long will it take? My train departs in thirty minutes.", "textUz": "Juda yaxshi! Qancha vaqt oladi? Poyezdim o'ttiz daqiqada jo'naydi."},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "Don't worry, we will be there in about fifteen minutes. Please fasten your seatbelt.", "textUz": "Xavotir olmang, 15 daqiqada yetib boramiz. Xavfsizlik kamarini taqing."},
                    {"speaker": "Passenger", "speakerIcon": "👨", "textTarget": "Here we are! Can I pay with credit card, and could I have a receipt?", "textUz": "Mana yetib keldik! Karta bilan to'lasam bo'ladimi va chek bera olasizmi?"},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "Certainly! Just tap your card. Total is eight dollars. Have a pleasant trip!", "textUz": "Albatta! Kartani tekkizing. Jami sakkiz dollar. Safaringiz xayrli bo'lsin!"},
                ]
            },
            {
                "id": "en_taxi_1",
                "title": "Ride-Hailing App in Heavy Rain (Yomg'irda ilova orqali taksi chaqirish)",
                "situationUz": "Kuchli yomg'irda ilova orqali taksi buyurtma qilib, haydovchi bilan uchrashish.",
                "targetWords": ["Location", "Umbrella", "Luggage", "Trunk", "Confirm"],
                "lines": [
                    {"speaker": "Passenger", "speakerIcon": "🌧️", "textTarget": "Hello! I am standing under the green awning near the coffee shop entrance.", "textUz": "Salom! Men qahvaxona kirishidagi yashil soyabon ostida turibman."},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "I see you! I am in the silver sedan with hazard lights flashing right across the street.", "textUz": "Ko'rdim sizni! Ko'chaning narigi tomonidagi avariya chiroqlari yoqilgan kumush mashinadaman."},
                    {"speaker": "Passenger", "speakerIcon": "🌧️", "textTarget": "Thank you for coming so fast! Could you open the trunk for my suitcase?", "textUz": "Tez kelganingiz uchun rahmat! Chamadonim uchun yukxonani ocha olasizmi?"},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "All set! Please close the door carefully. Destination is the Grand City Hotel, correct?", "textUz": "Tayyor! Eshikni mahkam yoping. Manzilingiz Grand City mehmonxonasi, to'g'rimi?"},
                    {"speaker": "Passenger", "speakerIcon": "🌧️", "textTarget": "Yes, that is right. Please turn up the heater a bit if possible.", "textUz": "Ha, xuddi shunday. Iloji bo'lsa pechkani sal ko'tarib bersangiz."},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "Right away. Sit back and dry off, we will be there safely shortly.", "textUz": "Hozirning o'zida. O'tirib isinib oling, tez orada xavfsiz yetib boramiz."},
                ]
            },
            {
                "id": "en_taxi_2",
                "title": "Late Night Airport Express (Tungi aeroport tezyurar taksisi)",
                "situationUz": "Kechki payt aeroportga borish uchun tezyurar taksidan foydalanish.",
                "targetWords": ["Terminal", "Highway", "Express", "Departure", "Toll"],
                "lines": [
                    {"speaker": "Passenger", "speakerIcon": "🌙", "textTarget": "Good evening! Which terminal do international flights depart from?", "textUz": "Xayrli kech! Xalqaro reyslar qaysi terminaldan uchadi?"},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "International flights depart from Terminal 2. Which airline are you flying with?", "textUz": "Xalqaro reyslar 2-terminaldan uchadi. Qaysi aviakompaniyada uchyapsiz?"},
                    {"speaker": "Passenger", "speakerIcon": "🌙", "textTarget": "Turkish Airlines. Can we take the toll highway to avoid traffic lights?", "textUz": "Turk Havo Yo'llari. Svetoforlarni chetlab o'tish uchun pullik trassadan yursak bo'ladimi?"},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "Yes, taking the highway will save us twenty minutes. I will take the express lane.", "textUz": "Ha, trassadan yursak yigirma daqiqa yutamiz. Tezyurar yo'lakdan ketaman."},
                    {"speaker": "Passenger", "speakerIcon": "🌙", "textTarget": "Great! Please drop me off right at the departures gate.", "textUz": "Ajoyib! Meni to'g'ridan-to'g'ri jo'nab ketish eshigi yonida qoldiring."},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "Here is Terminal 2, departures area. Safe travels and have a great flight!", "textUz": "Mana 2-terminal, jo'nab ketish hududi. Xavfsiz sayohat va yoqimli parvoz tilayman!"},
                ]
            },
            {
                "id": "en_taxi_3",
                "title": "City Sightseeing Taxi (Shahar bo'ylab taksi sayohati)",
                "situationUz": "Mehmon shahar ko'rish uchun taksi haydovchisidan asosiy joylarni ko'rsatishni so'ramoqda.",
                "targetWords": ["Landmarks", "Attractions", "Meter", "Historic", "Square"],
                "lines": [
                    {"speaker": "Tourist", "speakerIcon": "📸", "textTarget": "Hi! Could you take me on a scenic route through the historic downtown?", "textUz": "Salom! Meni tarixiy shahar markazi bo'ylab chiroyli yo'ldan olib o'ta olasizmi?"},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "With pleasure! We will pass by the Old Town Hall and the central cathedral.", "textUz": "Jon deb! Qadimgi shahar hokimiyati va markaziy sobor yonidan o'tamiz."},
                    {"speaker": "Tourist", "speakerIcon": "📸", "textTarget": "Could you slow down near the main square so I can take a photo?", "textUz": "Asosiy maydon yonida rasmga tushishim uchun biroz sekinlasha olasizmi?"},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "Of course! I can even pull over for two minutes if you like.", "textUz": "Albatta! Xohlasangiz 2 daqiqaga chetga to'xtab turishim ham mumkin."},
                    {"speaker": "Tourist", "speakerIcon": "📸", "textTarget": "You are very kind. What does the meter show now?", "textUz": "Juda mehribonsiz. Taksimetr hozir qancha ko'rsatmoqda?"},
                    {"speaker": "Driver", "speakerIcon": "🚕", "textTarget": "Twelve dollars total. Hope you are enjoying your visit to our city!", "textUz": "Jami o'n ikki dollar. Shahrimizga tashrifingiz sizga manzur bo'lyapti deb umid qilaman!"},
                ]
            }
        ],
        "hotel": [
            {
                "id": "en_hotel_0",
                "title": "Hotel Check-in & Keycard (Mehmonxonaga joylashish)",
                "situationUz": "Mehmonxonada xonaga joylashish va nonushta vaqti haqida so'rash.",
                "targetWords": ["Reservation", "Keycard", "Elevator", "Breakfast", "Luggage"],
                "lines": [
                    {"speaker": "Guest", "speakerIcon": "🧳", "textTarget": "Good evening! I have a reservation under the name John Smith for three nights.", "textUz": "Xayrli kech! Jon Smit nomiga 3 kechaga band qilingan xonam bor edi."},
                    {"speaker": "Receptionist", "speakerIcon": "👩‍💼", "textTarget": "Welcome Mr. Smith! Here is your keycard for room 405 on the fourth floor.", "textUz": "Xush kelibsiz janob Smit! 4-qavatdagi 405-xona kalit-kartasi."},
                    {"speaker": "Guest", "speakerIcon": "🧳", "textTarget": "Thank you. What time is breakfast served in the morning?", "textUz": "Rahmat. Ertalab nonushta soat nechada beriladi?"},
                    {"speaker": "Receptionist", "speakerIcon": "👩‍💼", "textTarget": "Breakfast is open from seven to ten thirty in the restaurant on the ground floor.", "textUz": "Nonushta birinchi qavatdagi restoranda soat 7 dan 10:30 gacha bo'ladi."},
                ]
            },
            {
                "id": "en_hotel_1",
                "title": "Room Service & Extra Amenities (Xona xizmati)",
                "situationUz": "Xonaga qo'shimcha sochiq va kechki ovqat buyurtma qilish.",
                "targetWords": ["Towels", "Dinner", "Amenities", "Promptly", "Deliver"],
                "lines": [
                    {"speaker": "Guest", "speakerIcon": "📞", "textTarget": "Hello, front desk? Could we request two extra bath towels for room 405?", "textUz": "Salom, qabulxona? 405-xonaga 2 ta qo'shimcha vanna sochiqlari so'rasak bo'ladimi?"},
                    {"speaker": "Staff", "speakerIcon": "🛎️", "textTarget": "Certainly, sir. Housekeeping will deliver them within ten minutes.", "textUz": "Albatta, xizmat ko'rsatish xodimi ularni 10 daqiqada yetkazib beradi."},
                    {"speaker": "Guest", "speakerIcon": "📞", "textTarget": "Can we also order a club sandwich and hot tea to the room?", "textUz": "Xonaga klub sendvichi va issiq choy buyurtma qilsak ham bo'ladimi?"},
                    {"speaker": "Staff", "speakerIcon": "🛎️", "textTarget": "I will connect you directly to the kitchen right away. Enjoy your evening!", "textUz": "Sizni hoziroq oshxona bilan bog'layman. Kechangiz yoqimli o'tsin!"},
                ]
            }
        ],
        "restaurant": [
            {
                "id": "en_restaurant_0",
                "title": "Dinner Reservation & Ordering (Kechki ovqat buyurtmasi)",
                "situationUz": "Restoranda ovqat buyurtma qilish va tavsiyalarni so'rash.",
                "targetWords": ["Appetizer", "Specialty", "Beverage", "Delicious", "Dessert"],
                "lines": [
                    {"speaker": "Waiter", "speakerIcon": "🤵", "textTarget": "Good evening! Welcome to Bella Vista. Table for two by the terrace?", "textUz": "Xayrli kech! Bella Vistaga xush kelibsiz. Ayvon yonidagi ikki kishilik stolmi?"},
                    {"speaker": "Guest", "speakerIcon": "🍽️", "textTarget": "Yes please. What is the chef's specialty this evening?", "textUz": "Ha, iltimos. Bugun oshpazning qanday maxsus taomi bor?"},
                    {"speaker": "Waiter", "speakerIcon": "🤵", "textTarget": "Our pan-seared salmon with lemon herb risotto is exceptionally fresh today.", "textUz": "Limonli va ko'katli rizotto bilan pishirilgan losos balig'imiz bugun juda yangi."},
                    {"speaker": "Guest", "speakerIcon": "🍽️", "textTarget": "That sounds delicious! We will also start with the fresh garden salad.", "textUz": "Juda mazali eshitiladi! Boshlanishiga yangi sabzavotli salat ham olamiz."},
                ]
            }
        ],
        "airport": [
            {
                "id": "en_airport_0",
                "title": "Airport Check-in & Boarding Pass (Aeroportda ro'yxatdan o'tish)",
                "situationUz": "Aeroportda pasport va chiptani ko'rsatib, samolyotga chiqish talonini olish.",
                "targetWords": ["Passport", "Luggage", "Boarding Pass", "Gate", "Security"],
                "lines": [
                    {"speaker": "Traveler", "speakerIcon": "🧳", "textTarget": "Good morning! Here is my passport for flight BA 204 to London.", "textUz": "Xayrli tong! Mana London reysiga pasportim."},
                    {"speaker": "Agent", "speakerIcon": "👩‍💼", "textTarget": "Welcome! Are you checking any luggage today, or just carry-on bags?", "textUz": "Xush kelibsiz! Biror yuk topshirasizmi yoki faqat qo'l yuki bormi?"},
                    {"speaker": "Traveler", "speakerIcon": "🧳", "textTarget": "One checked bag and a backpack. Could I please get a window seat?", "textUz": "Bitta topshiriladigan yuk va ryukzak. Oyna yonidan joy olsa bo'ladimi?"},
                    {"speaker": "Agent", "speakerIcon": "👩‍💼", "textTarget": "Seat 14A is confirmed. Boarding begins at Gate B7 in forty minutes.", "textUz": "14A o'rindiq tasdiqlandi. Chiqish B7 darvozasida 40 daqiqada boshlanadi."},
                ]
            }
        ],
        "shopping": [
            {
                "id": "en_shopping_0",
                "title": "Grocery Market & Fresh Produce (Do'konda xarid)",
                "situationUz": "Do'konda mevalar narxini so'rab, xarid qilish.",
                "targetWords": ["Organic", "Discount", "Receipt", "Total", "Cashier"],
                "lines": [
                    {"speaker": "Shopper", "speakerIcon": "🛒", "textTarget": "Excuse me, are these organic apples fresh, and what is the price per kilo?", "textUz": "Kechirasiz, bu olma yangimi va kilosi qancha turadi?"},
                    {"speaker": "Clerk", "speakerIcon": "👨‍🌾", "textTarget": "They arrived this morning! Three dollars a kilo, with a twenty percent discount on two.", "textUz": "Bugun ertalab keldi! Kilosi 3 dollar, ikkita olsangiz 20 foiz chegirma bor."},
                    {"speaker": "Shopper", "speakerIcon": "🛒", "textTarget": "Great! I will take two kilos and a carton of almond milk.", "textUz": "Ajoyib! Ikki kilo olma va bodom suti olaman."},
                    {"speaker": "Cashier", "speakerIcon": "👩", "textTarget": "Your total is eight dollars and fifty cents. Would you like a shopping bag?", "textUz": "Jami 8 dollar 50 sent bo'ldi. Xarid paketi kerakmi?"},
                ]
            }
        ],
        "doctor": [
            {
                "id": "en_doctor_0",
                "title": "Doctor Clinic Consultation (Shifokor ko'rigi)",
                "situationUz": "Klinikada shifokorga bosh og'rig'i va holsizlikdan shikoyat qilish.",
                "targetWords": ["Symptoms", "Headache", "Prescription", "Rest", "Dosage"],
                "lines": [
                    {"speaker": "Doctor", "speakerIcon": "👩‍⚕️", "textTarget": "Good afternoon! What symptoms seem to be bothering you today?", "textUz": "Xayrli kun! Bugun sizni qanday alomatlar bezovta qilmoqda?"},
                    {"speaker": "Patient", "speakerIcon": "🤒", "textTarget": "I have had a throbbing headache and slight fever since yesterday evening.", "textUz": "Kechadan beri boshim qattiq og'riyapti va engil isitma bor."},
                    {"speaker": "Doctor", "speakerIcon": "👩‍⚕️", "textTarget": "Your temperature is slightly elevated. I will write a mild prescription.", "textUz": "Haroratingiz biroz ko'tarilgan. Yengil dori yozib beraman."},
                    {"speaker": "Patient", "speakerIcon": "🤒", "textTarget": "Thank you, doctor. How often should I take this medication?", "textUz": "Rahmat, doktor. Ushbu dorini kuniga necha marta ichishim kerak?"},
                ]
            }
        ],
        "bank": [
            {
                "id": "en_bank_0",
                "title": "Opening Bank Account & Cards (Bankda hisob ochish)",
                "situationUz": "Bankda xalqaro to'lov kartasini ochish.",
                "targetWords": ["Account", "Identification", "Deposit", "Currency", "Transfer"],
                "lines": [
                    {"speaker": "Customer", "speakerIcon": "💳", "textTarget": "Hello! I would like to open a multi-currency checking account today.", "textUz": "Salom! Men bugun ko'p valyutali hisob raqami ochmoqchi edim."},
                    {"speaker": "Banker", "speakerIcon": "👨‍💼", "textTarget": "Welcome! Please provide your passport and proof of local address.", "textUz": "Xush kelibsiz! Pasportingiz va manzilingizni tasdiqlovchi hujjatni bering."},
                    {"speaker": "Customer", "speakerIcon": "💳", "textTarget": "Here are my documents. Can I also apply for a contactless debit card?", "textUz": "Mana hujjatlarim. Kontaktsiz debet kartasiga ham ariza bersam bo'ladimi?"},
                    {"speaker": "Banker", "speakerIcon": "👨‍💼", "textTarget": "Yes, it will be linked immediately and ready for online banking.", "textUz": "Ha, u darhol ulanadi va onlayn banking uchun tayyor bo'ladi."},
                ]
            }
        ],
        "combo": [
            {
                "id": "en_combo_0",
                "title": "A Complete Day in Town (Shahar bo'ylab to'liq kun)",
                "situationUz": "Taksida borish, mehmonxonaga joylashish va restoranda ovqatlanish.",
                "targetWords": ["Destination", "Reservation", "Appetite", "City", "Journey"],
                "lines": [
                    {"speaker": "Traveler", "speakerIcon": "🚕", "textTarget": "Driver, please take me to the Grand Plaza Hotel in the city center.", "textUz": "Haydovchi, iltimos meni shahar markazidagi Grand Plaza mehmonxonasiga olib boring."},
                    {"speaker": "Driver", "speakerIcon": "👨‍💼", "textTarget": "Right away! The hotel has one of the best rooftop restaurants in town.", "textUz": "Hozirning o'zida! Bu mehmonxonaning tomida ajoyib restoran bor."},
                    {"speaker": "Traveler", "speakerIcon": "🍽️", "textTarget": "That sounds perfect, I will definitely reserve a table for dinner tonight!", "textUz": "Juda ajoyib, bugun kechki ovqat uchun albatta stol band qilaman!"},
                ]
            }
        ]
    },
    "ru": {
        "taxi": [
            {
                "id": "ru_taxi_0",
                "title": "Поездка на городском такси (Taksida yo'l yurish)",
                "situationUz": "Yo'lovchi shoshilinch vokzalga yetib olish uchun taksi to'xtatmoqda.",
                "targetWords": ["Вокзал", "Пробки", "Объезд", "Чек", "Оплата"],
                "lines": [
                    {"speaker": "Пассажир", "speakerIcon": "👨", "textTarget": "Доброе утро! Вы свободны? Мне нужно как можно скорее на Центральный вокзал.", "textUz": "Xayrli tong! Bo'shmisiz? Men tezroq Markaziy Vokzalga borishim kerak."},
                    {"speaker": "Водитель", "speakerIcon": "🚕", "textTarget": "Здравствуйте! Да, присаживайтесь. В центре пробки, но поедем в объезд.", "textUz": "Salom! Ha, o'tiring. Markazda tirbandlik, ammo aylanma yo'ldan ketamiz."},
                    {"speaker": "Пассажир", "speakerIcon": "👨", "textTarget": "Отлично! Сколько займёт дорога? Мой поезд отправляется через полчаса.", "textUz": "Ajoyib! Yo'l qancha vaqt oladi? Poyezdim yarim soatda jo'naydi."},
                    {"speaker": "Водитель", "speakerIcon": "🚕", "textTarget": "Не переживайте, доедем минут за пятнадцать. Пристегните ремень безопасности.", "textUz": "Xavotir olmang, 15 daqiqada yetamiz. Xavfsizlik kamarini taqing."},
                    {"speaker": "Пассажир", "speakerIcon": "👨", "textTarget": "Вот мы и на месте! Можно оплатить картой и получить квитанцию?", "textUz": "Mana yetib keldik! Karta bilan to'lab, chek olsam bo'ladimi?"},
                    {"speaker": "Водитель", "speakerIcon": "🚕", "textTarget": "Конечно! Приложите карту к терминалу. Счастливого пути!", "textUz": "Albatta! Kartani terminalga bosing. Safaringiz xayrli bo'lsin!"},
                ]
            },
            {
                "id": "ru_taxi_1",
                "title": "Заказ такси в сильный дождь (Yomg'irda taksi chaqirish)",
                "situationUz": "Kuchli yomg'ir paytida taksi chaqirish va haydovchi bilan uchrashish.",
                "targetWords": ["Дождь", "Багажник", "Адрес", "Маршрут", "Печка"],
                "lines": [
                    {"speaker": "Пассажир", "speakerIcon": "🌧️", "textTarget": "Здравствуйте! Я стою под навесом у входа в кофейню.", "textUz": "Salom! Men qahvaxona kirishidagi ayvon ostida turibman."},
                    {"speaker": "Водитель", "speakerIcon": "🚕", "textTarget": "Вижу вас! Я на серебристом седане с аварийными сигналами.", "textUz": "Ko'rdim sizni! Kumush rangli avariya chiroqlari yoqilgan mashinadaman."},
                    {"speaker": "Пассажир", "speakerIcon": "🌧️", "textTarget": "Спасибо за быструю подачу! Откройте, пожалуйста, багажник.", "textUz": "Tez kelganingiz uchun rahmat! Yukxonani ochib yuborsangiz."},
                    {"speaker": "Водитель", "speakerIcon": "🚕", "textTarget": "Готово! Ваш адрес — гостиница Гранд Сити, верно?", "textUz": "Tayyor! Manzilingiz Grand Siti mehmonxonasi, to'g'rimi?"},
                    {"speaker": "Пассажир", "speakerIcon": "🌧️", "textTarget": "Да, всё верно. Включите, пожалуйста, печку потеплее.", "textUz": "Ha, to'g'ri. Iltimos, pechkani issiqroq qilib bersangiz."},
                    {"speaker": "Водитель", "speakerIcon": "🚕", "textTarget": "С удовольствием. Согревайтесь, скоро будем на месте.", "textUz": "Jon deb. Isinib oling, tez orada yetib boramiz."},
                ]
            }
        ],
        "hotel": [
            {
                "id": "ru_hotel_0",
                "title": "Заселение в гостиницу (Mehmonxonaga joylashish)",
                "situationUz": "Mehmonxonada xonaga joylashish va kalit olish.",
                "targetWords": ["Бронь", "Ключ-карта", "Завтрак", "Лифт", "Этаж"],
                "lines": [
                    {"speaker": "Гость", "speakerIcon": "🧳", "textTarget": "Добрый вечер! У меня забронирован номер на имя Иван Петров на три ночи.", "textUz": "Xayrli kech! Ivan Petrov nomiga 3 kechaga xona band qilingan edi."},
                    {"speaker": "Администратор", "speakerIcon": "👩‍💼", "textTarget": "Добро пожаловать! Ваш номер 405 на четвёртом этаже. Вот электронный ключ.", "textUz": "Xush kelibsiz! 4-qavatdagi 405-xona. Mana elektron kalitingiz."},
                    {"speaker": "Гость", "speakerIcon": "🧳", "textTarget": "Спасибо. Во сколько у вас начинается завтрак?", "textUz": "Rahmat. Nonushta soat nechada boshlanadi?"},
                    {"speaker": "Администратор", "speakerIcon": "👩‍💼", "textTarget": "Завтрак накрывают в ресторане на первом этаже с семи до десяти утра.", "textUz": "Nonushta birinchi qavatdagi restoranda soat 7 dan 10 gacha bo'ladi."},
                ]
            }
        ],
        "restaurant": [
            {
                "id": "ru_restaurant_0",
                "title": "Заказ ужина в ресторане (Restoranda kechki ovqat)",
                "situationUz": "Restoranda ovqat buyurtma berish va xizmatchi bilan muloqot.",
                "targetWords": ["Меню", "Блюдо", "Официант", "Вкусно", "Счёт"],
                "lines": [
                    {"speaker": "Официант", "speakerIcon": "🤵", "textTarget": "Добрый вечер! Столик на двоих у окна?", "textUz": "Xayrli kech! Deraza yonidagi ikki kishilik stolmi?"},
                    {"speaker": "Гость", "speakerIcon": "🍽️", "textTarget": "Да, пожалуйста. Что вы порекомендуете из фирменных блюд?", "textUz": "Ha, iltimos. Maxsus taomlardan nimani tavsiya etasiz?"},
                    {"speaker": "Официант", "speakerIcon": "🤵", "textTarget": "Сегодня рекомендую запечённого лосося с овощами гриль.", "textUz": "Bugun gril sabzavotlari bilan pishirilgan lososni tavsiya qilaman."},
                    {"speaker": "Гость", "speakerIcon": "🍽️", "textTarget": "Отлично, берём! И принесите графин ягодного морса.", "textUz": "Ajoyib, olamiz! Va rezavor mevali mors ham keltiring."},
                ]
            }
        ]
    }
}


def generate_topic_dialogue(topic: str, scenario_idx: int, lang: str = "en") -> Dict[str, Any]:
    """
    Agar mavzudagi tayyor vaziyatlar tugasa, deterministik tarzda aynan shu
    mavzuga xos bo'lgan YANGI VA TO'LIQ vaziyat yaratib beradi.
    Mavzu hech qachon adashmaydi!
    """
    canon = normalize_topic(topic)
    meta = TOPIC_METADATA.get(canon, TOPIC_METADATA["taxi"])
    is_ru = (lang == "ru")

    scenario_num = scenario_idx + 1

    if is_ru:
        title = f"{meta['icon']} {meta['name']} — Ситуация №{scenario_num}"
        situation_uz = f"{meta['name']} mavzusidagi {scenario_num}-hayotiy real vaziyat va muloqot."
        target_words = ["Диалог", "Практика", "Выражения", "Уверенность", "Успех"]
        lines = [
            {"speaker": "Собеседник 1", "speakerIcon": meta["icon"], "textTarget": f"Здравствуйте! Давайте обсудим детали по теме «{meta['name']}».", "textUz": f"Assalomu alaykum! Keling, «{meta['name']}» mavzusi bo'yicha suhbatlashamiz."},
            {"speaker": "Собеседник 2", "speakerIcon": "🗣️", "textTarget": f"С удовольствием! В этой ситуации очень важно правильно подобрать нужные слова.", "textUz": "Jon deb! Bu vaziyatda to'g'ri so'zlarni tanlash juda muhim."},
            {"speaker": "Собеседник 1", "speakerIcon": meta["icon"], "textTarget": "Согласен. Чёткое произношение и практический диалог дают отличный результат.", "textUz": "Qo'shilaman. Aniq talaffuz va amaliy dialog ajoyib natija beradi."},
            {"speaker": "Собеседник 2", "speakerIcon": "🗣️", "textTarget": "Большое спасибо за полезную практику! Переходим к следующему шагу.", "textUz": "Foydali amaliyot uchun katta rahmat! Keyingi qadamga o'tamiz."},
        ]
    else:
        title = f"{meta['icon']} {meta['name']} — Scenario #{scenario_num}"
        situation_uz = f"{meta['name']} mavzusidagi {scenario_num}-hayotiy real vaziyat va muloqot."
        target_words = ["Context", "Fluency", "Phrases", "Confidence", "Progress"]
        lines = [
            {"speaker": "Speaker A", "speakerIcon": meta["icon"], "textTarget": f"Hello! Let us practice essential conversations regarding {meta['name']}.", "textUz": f"Salom! Keling, {meta['name']} mavzusi bo'yicha muhim jumlalarni mashq qilamiz."},
            {"speaker": "Speaker B", "speakerIcon": "🗣️", "textTarget": f"Gladly! Learning realistic vocabulary for this situation is incredibly helpful.", "textUz": "Jon deb! Bu vaziyat uchun hayotiy so'zlarni o'rganish juda foydali."},
            {"speaker": "Speaker A", "speakerIcon": meta["icon"], "textTarget": "Exactly. Speaking out loud improves both your memory and pronunciation.", "textUz": "Xuddi shunday. Ovoz chiqarib gapirish xotira va talaffuzni kuchaytiradi."},
            {"speaker": "Speaker B", "speakerIcon": "🗣️", "textTarget": "Thank you for the thorough lesson! Ready for the next practical step.", "textUz": "To'liq dars uchun rahmat! Keyingi amaliy qadamga tayyorman."},
        ]

    return {
        "id": f"{lang}_{canon}_gen_{scenario_idx}",
        "title": title,
        "situationUz": situation_uz,
        "targetWords": target_words,
        "lines": lines
    }


def get_dialogues_for_topic(topic: str, lang: str = "en") -> List[Dict[str, Any]]:
    """Mavzuga tegishli barcha dialoglar ro'yxatini qaytaradi."""
    canon = normalize_topic(topic)
    target_lang = "ru" if lang == "ru" else "en"
    lang_db = DIALOGUES_DB.get(target_lang, DIALOGUES_DB["en"])
    
    dialogues = lang_db.get(canon, [])
    # Agar tayyor dialoglar 3 tadan kam bo'lsa, mavzuga xos generatsiya qilib to'ldiramiz
    results = list(dialogues)
    while len(results) < 3:
        results.append(generate_topic_dialogue(canon, len(results), target_lang))
    return results


def get_active_dialogue(topic: str, scenario_idx: int = 0, lang: str = "en") -> Dict[str, Any]:
    """Mavzu va vaziyat indeksi bo'yicha dialogni oladi."""
    dialogues = get_dialogues_for_topic(topic, lang)
    if 0 <= scenario_idx < len(dialogues):
        return dialogues[scenario_idx]
    return generate_topic_dialogue(topic, scenario_idx, lang)


def format_dialogue_telegram_message(
    dialogue: Dict[str, Any],
    current_step: int,
    topic: str,
    scenario_idx: int,
    lang: str = "en"
) -> str:
    """Telegram xabari ko'rinishida dialogni chiroyli formatlaydi."""
    canon = normalize_topic(topic)
    meta = TOPIC_METADATA.get(canon, TOPIC_METADATA["taxi"])
    lines = dialogue.get("lines", [])
    total_steps = len(lines)
    step = min(max(0, current_step), max(0, total_steps - 1))
    lang_flag = "🇷🇺 RU" if lang == "ru" else "🇬🇧 EN"

    # Progress bar: masalan 5 tadan 3 tasi [🟩🟩🟩⬜⬜]
    filled = "🟩" * (step + 1)
    empty = "⬜" * max(0, total_steps - (step + 1))
    progress_bar = f"[{filled}{empty}] {step + 1}/{total_steps}"

    current_line = lines[step] if step < len(lines) else lines[-1]

    kw_str = ", ".join([f"<code>{w}</code>" for w in dialogue.get("targetWords", [])])

    text = (
        f"🗣️ <b>Mnemonic Jonli Dialoglar Tizimi</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Mavzu:</b> {meta['icon']} <b>{meta['name']}</b>\n"
        f"📍 <b>Vaziyat {scenario_idx + 1}:</b> <i>{dialogue.get('title')}</i>\n"
        f"📝 <b>Holat:</b> {dialogue.get('situationUz')}\n"
        f"🌐 <b>O'rganish tili:</b> {lang_flag}\n"
        f"📊 <b>Dialog qadami:</b> {progress_bar}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💬 <b>Hozirgi replika (Qadam {step + 1}):</b>\n"
        f"{current_line['speakerIcon']} <b>{current_line['speaker']}:</b>\n"
        f"👉 <b>«{current_line['textTarget']}»</b>\n\n"
        f"🇺🇿 <b>Tarjimasi:</b>\n"
        f"<i>«{current_line['textUz']}»</i>\n\n"
        f"💡 <b>Kalit so'zlar:</b> {kw_str}\n\n"
        f"<i>Tugmalar orqali navbatdagi replikaga yoki aynan shu mavzudagi keyingi vaziyatga o'ting:</i>"
    )
    return text
