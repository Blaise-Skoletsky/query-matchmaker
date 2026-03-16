"""Golden reference data for evaluation tests."""

# ---------------------------------------------------------------------------
# SUMMARY_GOLDEN
# Format: (history: list[dict], reference: str, required_keywords: list[str])
# ---------------------------------------------------------------------------
SUMMARY_GOLDEN = [
    # Standard buy with multi-attribute item
    (
        [
            {"role": "user", "content": "I'm looking for a laptop"},
            {"role": "assistant", "content": "What brand, specs, and budget are you considering?"},
            {"role": "user", "content": "MacBook Pro 16-inch, M3 chip, under $2000"},
            {"role": "assistant", "content": "Any preference on storage or RAM?"},
            {"role": "user", "content": "At least 16GB RAM and 512GB storage"},
        ],
        "I want to buy a MacBook Pro 16-inch with M3 chip, 16GB RAM, 512GB storage, under $2000.",
        ["buy", "macbook", "m3", "2000", "16", "512"],
    ),
    # Sell with specific asking price
    (
        [
            {"role": "user", "content": "Selling my car"},
            {"role": "assistant", "content": "What make, model, and year?"},
            {"role": "user", "content": "2020 Toyota Camry, about 32,000 miles"},
            {"role": "assistant", "content": "What are you asking for it?"},
            {"role": "user", "content": "Asking $18,500, negotiable"},
        ],
        "I want to sell my 2020 Toyota Camry with 32,000 miles for $18,500.",
        ["sell", "toyota", "camry", "18500", "32000", "2020"],
    ),
    # Tool call in history — summary must ignore tool data
    (
        [
            {"role": "user", "content": "I want to buy a gaming PC"},
            {"role": "tool", "content": '{"prices": [{"model": "RTX 4090 build", "avg_price": 3200}]}'},
            {"role": "assistant", "content": "What GPU and budget are you looking for?"},
            {"role": "user", "content": "RTX 4080, under $2500 total"},
        ],
        "I want to buy a gaming PC with an RTX 4080 under $2500.",
        ["buy", "gaming", "rtx", "2500", "4080"],
    ),
    # User vague / doesn't answer clarifying question
    (
        [
            {"role": "user", "content": "Selling my phone"},
            {"role": "assistant", "content": "What model and condition?"},
            {"role": "user", "content": "iPhone 15 Pro, 256GB, like new"},
            {"role": "assistant", "content": "What price are you asking?"},
            {"role": "user", "content": "I don't know, anything is fine, reasonable offer"},
        ],
        "I want to sell my iPhone 15 Pro 256GB in like-new condition.",
        ["sell", "iphone", "256", "15", "pro"],
    ),
    # User changes their mind mid-conversation
    (
        [
            {"role": "user", "content": "I want to buy a road bike"},
            {"role": "assistant", "content": "What brand and budget?"},
            {"role": "user", "content": "Actually, I changed my mind — I want a mountain bike instead"},
            {"role": "assistant", "content": "Got it. What size and budget for a mountain bike?"},
            {"role": "user", "content": "29-inch wheels, under $800"},
        ],
        "I want to buy a mountain bike with 29-inch wheels under $800.",
        ["buy", "mountain", "bike", "800", "29"],
    ),
    # Longer conversation (6 turns), sell
    (
        [
            {"role": "user", "content": "Selling some furniture"},
            {"role": "assistant", "content": "What piece of furniture?"},
            {"role": "user", "content": "A dining table"},
            {"role": "assistant", "content": "What material, size, and how many seats?"},
            {"role": "user", "content": "Solid oak, seats 6 to 8 people"},
            {"role": "assistant", "content": "What condition is it in and what price are you asking?"},
            {"role": "user", "content": "Good condition, minor scratches, asking $600"},
        ],
        "I want to sell a solid oak dining table that seats 6-8 people in good condition for $600.",
        ["sell", "oak", "dining", "600", "6", "8"],
    ),
    # User rambles off-topic — summary should extract only buy/sell intent
    (
        [
            {"role": "user", "content": "Hey I'm moving next month so I need to get rid of stuff, anyway I have this guitar"},
            {"role": "assistant", "content": "What type of guitar and what condition is it in?"},
            {"role": "user", "content": "Electric, Fender Stratocaster, American Standard from 2018, great shape"},
            {"role": "assistant", "content": "What price are you asking?"},
            {"role": "user", "content": "Was thinking around $900 but might take $800, I just need it gone before the move"},
        ],
        "I want to sell a 2018 Fender Stratocaster American Standard electric guitar for $900.",
        ["sell", "fender", "stratocaster", "guitar", "2018", "american", "standard"],
    ),
    # Buy with urgency and condition preference
    (
        [
            {"role": "user", "content": "I need a PS5 ASAP"},
            {"role": "assistant", "content": "Any preference on condition or bundle?"},
            {"role": "user", "content": "Preferably with extra controllers, open to used if in good shape"},
            {"role": "assistant", "content": "What's your budget?"},
            {"role": "user", "content": "Up to $450"},
        ],
        "I want to buy a PS5, preferably with extra controllers, used in good condition, under $450.",
        ["buy", "ps5", "450", "controllers", "good", "condition"],
    ),
    # Tool call + vague user
    (
        [
            {"role": "user", "content": "Looking for a winter jacket"},
            {"role": "assistant", "content": "Let me check popular brands."},
            {"role": "tool", "content": '{"brands": ["North Face", "Patagonia", "Columbia"]}'},
            {"role": "assistant", "content": "What size and brand do you prefer?"},
            {"role": "user", "content": "Large, North Face or Patagonia, doesn't matter"},
            {"role": "assistant", "content": "What's your budget?"},
            {"role": "user", "content": "Under $300"},
        ],
        "I want to buy a large North Face or Patagonia winter jacket under $300.",
        ["buy", "jacket", "north face", "patagonia", "300", "large"],
    ),
    # Sell with make/model/year/mileage/price all mentioned
    (
        [
            {"role": "user", "content": "Selling my motorcycle"},
            {"role": "assistant", "content": "What make, model, and year?"},
            {"role": "user", "content": "2019 Honda CB500F, about 8,000 miles"},
            {"role": "assistant", "content": "Condition and asking price?"},
            {"role": "user", "content": "Excellent condition, asking $5,200"},
        ],
        "I want to sell my 2019 Honda CB500F motorcycle with 8,000 miles in excellent condition for $5,200.",
        ["sell", "honda", "cb500f", "5200", "8000", "excellent", "condition"],
    ),
    # Buy, user says "anything is fine" for non-critical attribute
    (
        [
            {"role": "user", "content": "Need a standing desk"},
            {"role": "assistant", "content": "What width and color?"},
            {"role": "user", "content": "60 inches wide, color doesn't matter"},
            {"role": "assistant", "content": "Electric or manual height adjustment?"},
            {"role": "user", "content": "Electric, budget around $400"},
        ],
        "I want to buy a 60-inch electric standing desk for around $400.",
        ["buy", "standing", "desk", "400", "60", "electric"],
    ),
    # Short conversation sell, specific price
    (
        [
            {"role": "user", "content": "Selling homemade sourdough bread"},
            {"role": "assistant", "content": "What size loaves and price per loaf?"},
            {"role": "user", "content": "850g loaves, $12 each, pickup only"},
        ],
        "I want to sell homemade sourdough bread in 850g loaves for $12 each, pickup only.",
        ["sell", "sourdough", "bread", "12", "850g", "pickup"],   
    ),
]


# ---------------------------------------------------------------------------
# INTENT_GOLDEN
# Format: (query_text: str, expected_intent: "buy" | "sell")
# Mix of first-person synthesized summaries and raw/unformatted queries
# ---------------------------------------------------------------------------
INTENT_GOLDEN = [
    # First-person summary format (from conversation router)
    ("I want to buy a MacBook Pro 16-inch with M3 chip under $2000.", "buy"),
    ("I want to sell my 2020 Toyota Camry with 32,000 miles for $18,500.", "sell"),
    ("I want to buy a PS5 with extra controllers, used in good condition, under $450.", "buy"),
    ("I want to sell my 2019 Honda CB500F motorcycle in excellent condition for $5,200.", "sell"),
    ("I want to buy a 60-inch electric standing desk for around $400.", "buy"),
    ("I want to sell my iPhone 15 Pro 256GB in like-new condition.", "sell"),
    ("I want to buy a mountain bike with 29-inch wheels under $800.", "buy"),
    ("I want to sell a solid oak dining table that seats 6-8 people for $600.", "sell"),
    # Raw / unformatted queries, these shouldn't appear, but we should be robust to them 
    ("selling ps5 $350", "sell"),
    ("need a bike asap", "buy"),
    ("offloading my furniture", "sell"),
    ("looking for running shoes size 10", "buy"),
    ("getting rid of old textbooks", "sell"),
    ("in the market for a used car", "buy"),
    ("listing my guitar for sale", "sell"),
    ("want a Nintendo Switch", "buy"),
    ("selling 2018 fender stratocaster", "sell"),
    # Ambiguous phrasing with clear intent, these shouldn't appear, but we should be robust to them 
    ("I could really use a new laptop for work", "buy"),
    ("trying to find someone who needs my old couch", "sell"),
    ("anyone selling vintage records nearby?", "buy"),
]


# ---------------------------------------------------------------------------
# CATEGORY_GOLDEN
# Format: (query_text: str, expected_category: str)
# Mix of first-person summaries and raw/unformatted queries
# ---------------------------------------------------------------------------
CATEGORY_GOLDEN = [
    # First-person summaries
    ("I want to buy a MacBook Pro 16-inch with M3 chip under $2000.", "electronics"),
    ("I want to sell my 2020 Toyota Camry with 32,000 miles for $18,500.", "vehicles"),
    ("I want to buy a large North Face winter jacket under $300.", "clothing"),
    ("I want to sell a solid oak dining table that seats 6-8 people for $600.", "furniture"),
    ("I want to sell a 2018 Fender Stratocaster electric guitar for $900.", "music"),
    ("I want to sell homemade sourdough bread for $12 per loaf.", "food"),
    ("I want to buy a mountain bike with 29-inch wheels under $800.", "sports"),
    ("I want to sell my iPhone 15 Pro 256GB in like-new condition.", "electronics"),
    ("I want to buy a pair of running shoes, size 10, under $120.", "clothing"),
    ("I want to sell my college textbooks from last semester.", "books"),
    # Raw / unformatted queries
    ("ps5 for sale $350", "electronics"),
    ("selling 2019 Honda CB500F motorcycle 8k miles", "vehicles"),
    ("looking for a sofa", "furniture"),
    ("want to buy a camera", "electronics"),
    ("selling fresh organic apples $3/lb", "food"),
    ("need running shoes size 10", "clothing"),
    ("selling old textbooks cheap", "books"),
    ("60-inch standing desk electric for sale", "furniture"),
    ("selling Fender Stratocaster guitar", "music"),
    ("mountain bike 29er for sale", "sports"),
]

# ---------------------------------------------------------------------------
# SCORING_PAIRS
# Format: (source_dict, candidate_dict, expected_score_min, expected_score_max)
# source has: id, intent, raw_text, attributes, required_match_attributes, preferred_match_attributes
# candidate has: id, intent, raw_text, attributes
# ---------------------------------------------------------------------------
SCORING_PAIRS = [
    # --- Product Match ---
    (
        {
            "id": "src_0",
            "intent": "buy",
            "raw_text": "I want to buy a MacBook Pro 16-inch with M3 chip under $2000.",
            "attributes": {"model": "macbook pro", "chip": "m3", "size": "16-inch", "budget": 2000},
            "required_match_attributes": ["model"],
            "preferred_match_attributes": ["chip", "size"],
        },
        {
            "id": "cand_0",
            "intent": "sell",
            "raw_text": "I want to sell my MacBook Pro 16-inch M3, excellent condition, asking $1800.",
            "attributes": {"model": "macbook pro", "chip": "m3", "size": "16-inch", "price": 1800, "condition": "excellent"},
        },
        0.7, 1.0,
    ),
    (
        {
            "id": "src_1",
            "intent": "buy",
            "raw_text": "I want to buy a PS5 with extra controllers, used in good condition, under $450.",
            "attributes": {"product": "ps5", "condition": "good", "budget": 450},
            "required_match_attributes": ["product"],
            "preferred_match_attributes": ["condition"],
        },
        {
            "id": "cand_1",
            "intent": "sell",
            "raw_text": "Selling PS5 with 2 extra controllers, good condition, $400.",
            "attributes": {"product": "ps5", "controllers": 2, "condition": "good", "price": 400},
        },
        0.7, 1.0,
    ),
    (
        {
            "id": "src_2",
            "intent": "buy",
            "raw_text": "I want to buy a 2020 Toyota Camry under $20,000.",
            "attributes": {"make": "toyota", "model": "camry", "year": 2020, "budget": 20000},
            "required_match_attributes": ["make", "model"],
            "preferred_match_attributes": ["year"],
        },
        {
            "id": "cand_2",
            "intent": "sell",
            "raw_text": "I want to sell my 2020 Toyota Camry, 32,000 miles, for $18,500.",
            "attributes": {"make": "toyota", "model": "camry", "year": 2020, "mileage": 32000, "price": 18500},
        },
        0.7, 1.0,
    ),
    (
        {
            "id": "src_3",
            "intent": "buy",
            "raw_text": "I want to buy a MacBook Pro, any generation, under $1500.",
            "attributes": {"model": "macbook pro", "budget": 1500},
            "required_match_attributes": ["model"],
            "preferred_match_attributes": [],
        },
        {
            "id": "cand_3",
            "intent": "sell",
            "raw_text": "Selling MacBook Pro 14-inch M1 Pro, 2021, great condition, $1,400.",
            "attributes": {"model": "macbook pro", "chip": "m1 pro", "size": "14-inch", "year": 2021, "price": 1400},
        },
        0.7, 1.0,
    ),
    (
        {
            "id": "src_4",
            "intent": "buy",
            "raw_text": "I want to buy a mountain bike with 29-inch wheels under $800.",
            "attributes": {"type": "mountain bike", "wheel_size": "29-inch", "budget": 800},
            "required_match_attributes": ["type"],
            "preferred_match_attributes": ["wheel_size"],
        },
        {
            "id": "cand_4",
            "intent": "sell",
            "raw_text": "Selling Trek Marlin 7 mountain bike, 29er, 2022, excellent shape, $750.",
            "attributes": {"brand": "trek", "model": "marlin 7", "type": "mountain bike", "wheel_size": "29-inch", "year": 2022, "price": 750},
        },
        0.7, 1.0,
    ),
    (
        {
            "id": "src_5",
            "intent": "buy",
            "raw_text": "I want to buy a used Toyota sedan under $15,000.",
            "attributes": {"make": "toyota", "body_type": "sedan", "budget": 15000},
            "required_match_attributes": ["make"],
            "preferred_match_attributes": ["body_type"],
        },
        {
            "id": "cand_5",
            "intent": "sell",
            "raw_text": "Selling 2019 Toyota Camry, 45k miles, clean title, $13,800.",
            "attributes": {"make": "toyota", "model": "camry", "year": 2019, "mileage": 45000, "price": 13800},
        },
        0.7, 1.0,
    ),
    # --- No Product Match ---
    (
        {
            "id": "src_6",
            "intent": "buy",
            "raw_text": "I want to buy a laptop for creative work, under $1800.",
            "attributes": {"type": "laptop", "use_case": "creative", "budget": 1800},
            "required_match_attributes": [],
            "preferred_match_attributes": ["type"],
        },
        {
            "id": "cand_6",
            "intent": "sell",
            "raw_text": "Selling Microsoft Surface Pro 9, with keyboard, $1,200.",
            "attributes": {"brand": "microsoft", "model": "surface pro 9", "type": "tablet", "price": 1200},
        },
        0.0, 0.69,
    ),
    (
        {
            "id": "src_7",
            "intent": "buy",
            "raw_text": "I want to buy an acoustic guitar under $500.",
            "attributes": {"type": "acoustic guitar", "budget": 500},
            "required_match_attributes": ["type"],
            "preferred_match_attributes": [],
        },
        {
            "id": "cand_7",
            "intent": "sell",
            "raw_text": "Selling a Fender Stratocaster electric guitar, 2018, $900.",
            "attributes": {"brand": "fender", "model": "stratocaster", "type": "electric guitar", "year": 2018, "price": 900},
        },
        0.0, 0.69,
    ),
    (
        {
            "id": "src_8",
            "intent": "buy",
            "raw_text": "I want to buy an SUV under $25,000.",
            "attributes": {"body_type": "suv", "budget": 25000},
            "required_match_attributes": ["body_type"],
            "preferred_match_attributes": [],
        },
        {
            "id": "cand_8",
            "intent": "sell",
            "raw_text": "Selling 2021 Honda Civic sedan, 28k miles, $19,500.",
            "attributes": {"make": "honda", "model": "civic", "body_type": "sedan", "year": 2021, "price": 19500},
        },
        0.0, 0.69,
    ),
    (
        {
            "id": "src_9",
            "intent": "buy",
            "raw_text": "I want to buy a gaming laptop with RTX 4080 under $2500.",
            "attributes": {"type": "laptop", "gpu": "rtx 4080", "use_case": "gaming", "budget": 2500},
            "required_match_attributes": ["type"],
            "preferred_match_attributes": ["gpu"],
        },
        {
            "id": "cand_9",
            "intent": "sell",
            "raw_text": "Selling a solid oak dining table that seats 6-8 people for $600.",
            "attributes": {"type": "dining table", "material": "oak", "seats": 8, "price": 600},
        },
        0.0, 0.69,
    ),
    (
        {
            "id": "src_10",
            "intent": "buy",
            "raw_text": "I want to buy fresh organic produce.",
            "attributes": {"category": "food", "type": "produce", "preference": "organic"},
            "required_match_attributes": [],
            "preferred_match_attributes": ["type"],
        },
        {
            "id": "cand_10",
            "intent": "sell",
            "raw_text": "Selling 2020 Toyota Camry, 32,000 miles, $18,500.",
            "attributes": {"make": "toyota", "model": "camry", "year": 2020, "price": 18500},
        },
        0.0, 0.69,
    ),
    (
        {
            "id": "src_11",
            "intent": "buy",
            "raw_text": "I want to buy a pair of running shoes, size 10.",
            "attributes": {"type": "running shoes", "size": 10},
            "required_match_attributes": ["type"],
            "preferred_match_attributes": ["size"],
        },
        {
            "id": "cand_11",
            "intent": "sell",
            "raw_text": "Selling homemade sourdough bread, 850g loaves, $12 each.",
            "attributes": {"type": "bread", "variety": "sourdough", "weight": "850g", "price": 12},
        },
        0.0, 0.69,
    ),
]
