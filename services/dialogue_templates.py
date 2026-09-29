"""Topic-specific bilingual practice prompts (EN, RU, Uzbek)."""

TOPIC_PRACTICE = {
    "taxi": [
        ("Please take me to the station.", "Отвезите меня на вокзал, пожалуйста.", "Iltimos, meni vokzalga olib boring."),
        ("Can I pay for the taxi by card?", "Можно оплатить такси картой?", "Taksi haqini karta bilan to'lasam bo'ladimi?"),
        ("Could you put my luggage in the trunk?", "Положите мой багаж в багажник, пожалуйста.", "Iltimos, yukimni yukxonaga qo'ying."),
    ],
    "hotel": [
        ("I have a room reservation.", "У меня забронирован номер.", "Men xona band qilganman."),
        ("What time is breakfast at the hotel?", "Во сколько завтрак в гостинице?", "Mehmonxonada nonushta soat nechada?"),
        ("Could I check out an hour later?", "Можно выехать на час позже?", "Bir soat kechroq chiqishim mumkinmi?"),
    ],
    "restaurant": [
        ("Could I see the menu, please?", "Можно меню, пожалуйста?", "Iltimos, menyuni bersangiz."),
        ("Does this dish contain nuts?", "В этом блюде есть орехи?", "Bu taomda yong'oq bormi?"),
        ("Could we have the restaurant bill?", "Можно нам счёт?", "Hisobni olib kelsangiz."),
    ],
    "airport": [
        ("Where is the check-in counter for my flight?", "Где стойка регистрации на мой рейс?", "Parvozim uchun ro'yxatdan o'tish joyi qayerda?"),
        ("Is this baggage included in my ticket?", "Этот багаж включён в билет?", "Bu yuk chipta narxiga kiradimi?"),
        ("Which gate does my flight depart from?", "Из какого выхода отправляется мой рейс?", "Parvozimga qaysi chiqishdan o'taman?"),
    ],
    "shopping": [
        ("How much does this shirt cost?", "Сколько стоит эта рубашка?", "Bu ko'ylak qancha turadi?"),
        ("Do you have a larger size?", "У вас есть размер побольше?", "Kattaroq o'lchami bormi?"),
        ("Can I return this purchase with my receipt?", "Можно вернуть покупку с чеком?", "Xaridni chek bilan qaytarsam bo'ladimi?"),
    ],
    "doctor": [
        ("I would like to book a doctor's appointment.", "Я хочу записаться к врачу.", "Shifokor qabuliga yozilmoqchiman."),
        ("I have had a headache since yesterday.", "У меня со вчерашнего дня болит голова.", "Kechadan beri boshim og'riyapti."),
        ("How often should I take this medicine?", "Как часто принимать это лекарство?", "Bu dorini qanchalik tez-tez ichish kerak?"),
    ],
    "bank": [
        ("I would like to open a bank account.", "Я хочу открыть банковский счёт.", "Bank hisobini ochmoqchiman."),
        ("What is today's exchange rate?", "Какой сегодня обменный курс?", "Bugungi valyuta kursi qancha?"),
        ("I lost my bank card. Please block it.", "Я потерял банковскую карту. Заблокируйте её, пожалуйста.", "Bank kartam yo'qoldi. Iltimos, uni bloklang."),
    ],
    "combo": [
        ("Please take a taxi to our hotel.", "Поезжайте на такси в нашу гостиницу, пожалуйста.", "Iltimos, mehmonxonamizga taksida boring."),
        ("Can the hotel book a restaurant table?", "Может гостиница забронировать столик в ресторане?", "Mehmonxona restorandan stol band qila oladimi?"),
        ("After dinner, we need a taxi to the airport.", "После ужина нам нужно такси в аэропорт.", "Kechki ovqatdan keyin aeroportga taksi kerak."),
    ],
}
