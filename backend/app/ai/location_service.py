import re
import unicodedata
from typing import Optional, List, Dict, Tuple
from rapidfuzz import fuzz

# ==============================================================================
# TAMIL NADU 38 DISTRICTS & COMPREHENSIVE SUB-DISTRICT / TOWN GEOGRAPHIC CATALOG
# Every entry explicitly maps to its official District with verified GPS Coordinates.
# ==============================================================================

TAMIL_NADU_DISTRICT_LOCATIONS: List[Dict] = [
    # --------------------------------------------------------------------------
    # 1. COIMBATORE DISTRICT (கோயம்புத்தூர்)
    # Structured official gazette master covering 3 Revenue Divisions, 11 Taluks,
    # and all official Revenue Villages & Localities.
    # --------------------------------------------------------------------------

    # --- MADUKKARAI TALUK (மடுக்கரை வட்டம்) ---
    {
        "name": "Madukkarai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.903000",
        "longitude": "76.963000",
        "keywords": ["madukkarai", "மதுக்கரை", "madukkarai market", "acc cement madukkarai", "madukkarai railway station"]
    },
    {
        "name": "Mavuthampathy, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.860000",
        "longitude": "76.880000",
        "keywords": ["mavuthampathy", "mavuthampathi", "மவுத்தம்பதி", "mavuthampatty", "navakkarai"]
    },
    {
        "name": "Pichanur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.875000",
        "longitude": "76.895000",
        "keywords": ["pichanur", "பிச்சனூர்", "pichanoor", "walayar border pichanur"]
    },
    {
        "name": "Seerapalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.915000",
        "longitude": "76.975000",
        "keywords": ["seerapalayam", "சீராபாளையம்", "seerapalayam pirivu"]
    },
    {
        "name": "Ettimadai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.900000",
        "longitude": "76.898000",
        "keywords": ["ettimadai", "எட்டிமடை", "amrita university ettimadai", "ettimadai railway station"]
    },
    {
        "name": "Thirumalayampalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.870000",
        "longitude": "76.910000",
        "keywords": ["thirumalayampalayam", "திருமலையம்பாளையம்", "thirumalaiyampalayam"]
    },
    {
        "name": "Vazhukuparai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.865000",
        "longitude": "76.935000",
        "keywords": ["vazhukuparai", "valukkupparai", "வழுக்குப்பாறை", "vazhukkuparai"]
    },
    {
        "name": "Malumichampatti, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.910000",
        "longitude": "76.985000",
        "keywords": ["malumichampatti", "மலுமிச்சம்பட்டி", "malumichampatty", "malumichampatti junction"]
    },
    {
        "name": "Palathurai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.895000",
        "longitude": "76.945000",
        "keywords": ["palathurai", "பாலத்துறை", "palathurai road"]
    },
    {
        "name": "Karunchamigoundenpalayam & Thammagoundanpalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.885000",
        "longitude": "76.955000",
        "keywords": ["karunchamigoundenpalayam", "கருஞ்சாமி கவுண்டன்பாளையம்", "thammagoundanpalayam", "தம்ம கவுண்டன்பாளையம்"]
    },
    {
        "name": "Nachipalayam & Arisipalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.880000",
        "longitude": "76.920000",
        "keywords": ["nachipalayam", "நாச்சிபாளையம்", "arisipalayam", "அரிசிபாளையம்", "arisi palayam"]
    },
    {
        "name": "Myleripalayam & Oorattukuppai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.890000",
        "longitude": "77.010000",
        "keywords": ["myleripalayam", "மயிலேரிபாளையம்", "oorattukuppai", "ஊரட்டுக்குப்பை", "orattukuppai"]
    },
    {
        "name": "Othakkalmandapam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.885000",
        "longitude": "76.975000",
        "keywords": ["othakkalmandapam", "ஒத்தக்கால்மண்டபம்", "othakkalmandapam junction", "premier mills"]
    },
    {
        "name": "Chettypalayam (Chettipalayam), Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.880000",
        "longitude": "77.030000",
        "keywords": ["chettypalayam", "chettipalayam", "செட்டிப்பாளையம்", "kari motor speedway"]
    },
    {
        "name": "Kurichi & Eachanari, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.942700",
        "longitude": "76.965400",
        "keywords": ["kurichy", "kurichi", "குறிச்சி", "eachanari", "ஈச்சனாரி", "sidco coimbatore", "sundarapuram", "சுந்தராபுரம்"]
    },
    {
        "name": "Vellalur (Vellalore), Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.963400",
        "longitude": "76.994000",
        "keywords": ["vellalur", "vellalore", "வெள்ளலூர்", "podanur", "போத்தனூர்"]
    },

    # --- PERUR TALUK (பேரூர் வட்டம்) ---
    {
        "name": "Ikkaraipoluvampatty & Madavarayapuram, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.950000",
        "longitude": "76.780000",
        "keywords": ["ikkaraipoluvampatty", "இக்கரை பூளுவாம்பட்டி", "ikkaraiboluampatti", "madavarayapuram", "மாதவராயபுரம்"]
    },
    {
        "name": "Alandurai & Pooluvampatti, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.930000",
        "longitude": "76.810000",
        "keywords": ["alandurai", "ஆலாந்துறை", "pooluvampatti", "pooluvapatti", "பூளுவம்பட்டி", "thenkarai", "தென்கரை"]
    },
    {
        "name": "Semmedu, Iruttupallam & Poondi, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.975000",
        "longitude": "76.735000",
        "keywords": ["semmedu", "செம்மேடு", "iruttupallam", "இருட்டுப்பள்ளம்", "poondi velliangiri", "பூண்டி", "velliangiri hills", "isha yoga center"]
    },
    {
        "name": "Madampatty & Theethipalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.965000",
        "longitude": "76.865000",
        "keywords": ["madampatty", "madampatti", "மாதம்பட்டி", "theethipalayam", "தீதிப்பாளையம்"]
    },
    {
        "name": "Perur Chettipalayam & Perur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.970000",
        "longitude": "76.910000",
        "keywords": ["perur", "பேரூர்", "perur chettipalayam", "பேரூர் செட்டிபாளையம்", "perur pateeswarar temple", "பேரூர் கோவில்"]
    },
    {
        "name": "Narasipuram & Vellimalaipattinam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.990000",
        "longitude": "76.840000",
        "keywords": ["narasipuram", "நரசிபுரம்", "vellimalaipattinam", "வெள்ளிமலைப்பட்டினம்", "vaidehi falls"]
    },
    {
        "name": "Jakirnaickenpalayam & Devarayanpuram, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.985000",
        "longitude": "76.820000",
        "keywords": ["jakirnaickenpalayam", "ஜாகீர்நாயக்கன்பாளையம்", "devarayanpuram", "தேவராயன்புரம்"]
    },
    {
        "name": "Thondamuthur & Thenamanallur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.990000",
        "longitude": "76.840000",
        "keywords": ["thondamuthur", "தொண்டாமுத்தூர்", "thenamanallur", "தேனமநல்லூர்", "muthurajapuram"]
    },
    {
        "name": "Kalikanaickenpalayam & Vadavalli, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.027000",
        "longitude": "76.904800",
        "keywords": ["kalikanaickenpalayam", "காளிகநாயக்கன்பாளையம்", "vadavalli", "வடவள்ளி", "marudhamalai", "மருதமலை", "navavoor", "bommanampalayam"]
    },
    {
        "name": "Chithirai Chavadi & Vedapatti, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.985000",
        "longitude": "76.890000",
        "keywords": ["chithirai chavadi", "சித்திரை சாவடி", "vedapatti", "வேடபட்டி", "dhaliyur", "தாளியூர்"]
    },
    {
        "name": "Sundakamuthur & Veerakeralam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.980000",
        "longitude": "76.920000",
        "keywords": ["sundakamuthur", "சுண்டக்காமுத்தூர்", "veerakeralam", "வீரகேரளம்", "sundakkamuthur"]
    },
    {
        "name": "Komarapalayam & Kuniyamuthur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.957600",
        "longitude": "76.957100",
        "keywords": ["komarapalayam", "குமாரபாளையம்", "kuniyamuthur", "குனியமுத்தூர்", "kuniamuthur", "kovaipudur", "கோவைப்புதூர்"]
    },

    # --- SULUR TALUK (சூலூர் வட்டம்) ---
    {
        "name": "Paduvampalli & Kaduvettipalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.080000",
        "longitude": "77.160000",
        "keywords": ["paduvampalli", "படுவம்பள்ளி", "kaduvettipalayam", "கடுவெட்டிபாளையம்"]
    },
    {
        "name": "Mopperipalayam & Kittampalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.095000",
        "longitude": "77.190000",
        "keywords": ["mopperipalayam", "மொப்பிரிபாளையம்", "kittampalayam", "கிட்டாம்பாளையம்"]
    },
    {
        "name": "Semmandampalayam & Karumathampatty, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.110000",
        "longitude": "77.180000",
        "keywords": ["semmandampalayam", "செம்மண்டாம்பாளையம்", "karumathampatty", "karumathampatti", "கருமத்தம்பட்டி", "somanur", "சோமனூர்"]
    },
    {
        "name": "Kaniyur & Arasur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.070000",
        "longitude": "77.130000",
        "keywords": ["kaniyur", "கணியூர்", "arasur", "அரசூர்"]
    },
    {
        "name": "Neelambur & Mylampatty, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.055000",
        "longitude": "77.085000",
        "keywords": ["neelambur", "நீலம்பூர்", "mylampatty", "மயிலாம்பட்டி", "avinashi road bypass"]
    },
    {
        "name": "Irugur & Chinniyampalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.020000",
        "longitude": "77.065000",
        "keywords": ["irugur", "இருகூர்", "chinniyampalayam", "சின்னியம்பாளையம்", "goldwins", "கோல்ட்வின்ஸ்"]
    },
    {
        "name": "Rasipalayam & Kadampadi, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.010000",
        "longitude": "77.110000",
        "keywords": ["rasipalayam", "ராசிபாளையம்", "kadampadi", "கடம்பாடி"]
    },
    {
        "name": "Kangayampalayam & Sulur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.025000",
        "longitude": "77.127000",
        "keywords": ["kangayampalayam", "காங்கேயம்பாளையம்", "sulur", "சூலூர்", "sulur air force base"]
    },
    {
        "name": "Kannampalayam & Otterpalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.000000",
        "longitude": "77.100000",
        "keywords": ["kannampalayam", "கண்ணம்பாளையம்", "otterpalayam", "ஒட்டர் பாளையம்", "pallapalayam", "பல்லபாளையம்"]
    },
    {
        "name": "Pattanam & Peedampalli, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.970000",
        "longitude": "77.070000",
        "keywords": ["pattanam", "பட்டணம்", "peedampalli", "பீடம்பள்ளி", "pattanam itanagar"]
    },
    {
        "name": "Kallengal & Pappampatty, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.980000",
        "longitude": "77.120000",
        "keywords": ["kallengal", "கல்லேங்கல்", "kallangal", "pappampatty", "பப்பம்பட்டி", "pappampatti"]
    },
    {
        "name": "Kallapalayam & Pachapalayam (Sulur), Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.960000",
        "longitude": "77.110000",
        "keywords": ["kallapalayam", "கள்ளப்பாளையம்", "pachapalayam sulur", "பச்சாபாளையம்"]
    },
    {
        "name": "Bogampatty & Idayapalayam (Sulur), Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.930000",
        "longitude": "77.150000",
        "keywords": ["bogampatty", "bogampatti", "போகம்பட்டி", "idayapalayam sulur", "இடையர்பாளையம் சூலூர்"]
    },
    {
        "name": "Selakkarichel & Varapatty, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.890000",
        "longitude": "77.170000",
        "keywords": ["selakkarichel", "செலாக்கரிச்சல்", "varapatty", "varapatti", "வரப்பட்டி", "sultanpet", "சுல்தான்பேட்டை"]
    },
    {
        "name": "Vadambacheri & Vadavedampatty, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.870000",
        "longitude": "77.180000",
        "keywords": ["vadambacheri", "வடம்பச்சேரி", "vadavedampatty", "வடவேடம்பட்டி"]
    },
    {
        "name": "Kumarapalayam (Sulur) & Malaipalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.860000",
        "longitude": "77.160000",
        "keywords": ["kumarapalayam sulur", "குமாரபாளையம் சூலூர்", "malaipalayam", "மலைப்பாளையம்"]
    },
    {
        "name": "S. Ayyampalayam & Kammalapatty, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.840000",
        "longitude": "77.150000",
        "keywords": ["s. ayyampalayam", "எஸ். அய்யம்பாளையம்", "kammalapatty", "கம்மாலபட்டி"]
    },
    {
        "name": "Jallipatty & Sencheripudur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.820000",
        "longitude": "77.170000",
        "keywords": ["jallipatty", "ஜல்லிபட்டி", "sencheripudur", "செஞ்சேரிபுதூர்", "senjerimalai", "செஞ்சேரிமலை"]
    },
    {
        "name": "Thalakari & J. Krishnapuram, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.800000",
        "longitude": "77.180000",
        "keywords": ["thalakari", "தளக்கரை", "j. krishnapuram", "ஜே. கிருஷ்ணாபுரம்", "j. krisnapuram"]
    },

    # --- COIMBATORE NORTH TALUK (கோயம்புத்தூர் வடக்கு வட்டம்) ---
    {
        "name": "Kalapatty & Vilankurichi, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.060000",
        "longitude": "77.030000",
        "keywords": ["kalapatty", "kalapatti", "காளப்பட்டி", "vilankurichi", "விளாங்குறிச்சி", "sharp nagar", "veeriyampalayam"]
    },
    {
        "name": "Saravanampatty & Chinnavedampatty, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.077200",
        "longitude": "76.997500",
        "keywords": ["saravanampatty", "saravanampatti", "சரவணம்பட்டி", "chinnavedampatty", "chinnavedampatti", "சின்னவேடம்பட்டி", "chil sez", "kct"]
    },
    {
        "name": "Vellakinar & Sanganur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.078400",
        "longitude": "76.938800",
        "keywords": ["vellakinar", "வெள்ளக்கினார்", "sanganur", "சங்கனூர்", "sanganur canal"]
    },
    {
        "name": "Ganapathy & Krishnarayapuram, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.038400",
        "longitude": "76.974400",
        "keywords": ["ganapathy", "கணபதி", "krishnarayapuram", "கிருஷ்ணராயபுரம்", "maniyakarampalayam", "sathy road"]
    },
    {
        "name": "Thelungupalayam & Puliyakulam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.010000",
        "longitude": "76.980000",
        "keywords": ["thelungupalayam", "telungupalayam", "தெலுங்குபாளையம்", "puliyakulam", "புலியகுளம்", "puliyakulam vinayagar"]
    },
    {
        "name": "Anupperpalayam & Naickenpalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.130000",
        "longitude": "76.940000",
        "keywords": ["anupperpalayam", "அனுப்பர்பாளையம்", "naickenpalayam", "நாயக்கன்பாளையம்"]
    },
    {
        "name": "Gudalur (Coimbatore) & Periyanaickenpalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.145000",
        "longitude": "76.935000",
        "keywords": ["gudalur coimbatore", "கூடலூர் கோவை", "periyanaickenpalayam", "பெரியநாயக்கன்பாளையம்", "pns palayam"]
    },
    {
        "name": "Veerapandi & Bilichi, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.160000",
        "longitude": "76.930000",
        "keywords": ["veerapandi coimbatore", "வீரபாண்டி", "bilichi", "பிலிச்சி"]
    },
    {
        "name": "Narasimhanaickenpalayam & Kurudampalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.100000",
        "longitude": "76.935000",
        "keywords": ["narasimhanaickenpalayam", "நரசிம்மநாயக்கன்பாளையம்", "nsn palayam", "kurudampalayam", "குருடம்பாளையம்"]
    },
    {
        "name": "Thudiyalur & Pannimadai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.078400",
        "longitude": "76.938800",
        "keywords": ["thudiyalur", "துடியலூர்", "pannimadai", "பன்னிமடை", "thoppampatti", "nggo colony"]
    },
    {
        "name": "Nanjundapuram & Chinnathadagam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.050000",
        "longitude": "76.880000",
        "keywords": ["nanjundapuram", "நஞ்சுண்டாபுரம்", "chinnathadagam", "thadagam", "சின்னத்தடாகம்", "somayampalayam", "சோமையம்பாளையம்", "kanuvai"]
    },
    {
        "name": "Goundenpalayam (Kavundampalayam) & Saibaba Colony, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.045000",
        "longitude": "76.935000",
        "keywords": ["goundenpalayam", "kavundampalayam", "koundampalayam", "கவுண்டம்பாளையம்", "saibaba colony", "சாயிபாபா காலனி", "edaiyarpalayam"]
    },

    # --- METTUPALAYAM TALUK (மேட்டுப்பாளையம் வட்டம்) ---
    {
        "name": "Nellithurai & Odanthurai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.300000",
        "longitude": "76.930000",
        "keywords": ["nellithurai", "நெல்லித்துறை", "odanthurai", "ஒடந்துறை", "mettupalayam", "மேட்டுப்பாளையம்", "black thunder"]
    },
    {
        "name": "Thekkampatty & Sikkadasampalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.310000",
        "longitude": "76.960000",
        "keywords": ["thekkampatty", "thekkampatti", "தேக்கம்பட்டி", "sikkadasampalayam", "chikkadasampalayam", "சிக்கதாசம்பாளையம்"]
    },
    {
        "name": "Sirumugai & Irumburai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.320000",
        "longitude": "77.000000",
        "keywords": ["sirumugai", "சிறுமுகை", "irumburai", "இரும்பறை", "alangombu", "ஆலங்கொம்பு"]
    },
    {
        "name": "Chinnakallipatty & Mooduthurai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.330000",
        "longitude": "77.020000",
        "keywords": ["chinnakallipatty", "சின்னக்கல்லிபட்டி", "mooduthurai", "மூடுதுறை"]
    },
    {
        "name": "Iluppanatham & Bellepalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.270000",
        "longitude": "76.980000",
        "keywords": ["iluppanatham", "இலுப்பநத்தம்", "bellepalayam", "பெள்ளேபாளையம்"]
    },
    {
        "name": "Jadayampalayam & Kemmarampalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.250000",
        "longitude": "76.990000",
        "keywords": ["jadayampalayam", "ஜடையம்பாளையம்", "kemmarampalayam", "கெம்மாரம்பாளையம்"]
    },
    {
        "name": "Tholampalayam & Velliyankadu, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.230000",
        "longitude": "76.880000",
        "keywords": ["tholampalayam", "தோலம்பாளையம்", "velliyankadu", "வெள்ளியங்காடு", "pillur dam", "பிள்ளூர் அணை"]
    },
    {
        "name": "Kalampalayam & Marudur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.260000",
        "longitude": "76.940000",
        "keywords": ["kalampalayam", "காளம்பாளையம்", "marudur mettupalayam", "மருதூர் மேட்டுப்பாளையம்"]
    },
    {
        "name": "Karamadai, Bellathi & Sikkarampalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.240000",
        "longitude": "76.960000",
        "keywords": ["karamadai", "காரமடை", "bellathi", "பெள்ளாதி", "sikkarampalayam", "சிக்காரம்பாளையம்", "karamadai ranganathar"]
    },

    # --- ANNUR TALUK (அன்னூர் வட்டம்) ---
    {
        "name": "Annur & Pillayampalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.233300",
        "longitude": "77.133300",
        "keywords": ["annur", "அன்னூர்", "pillayampalayam", "பிள்ளையம்பாளையம்", "annur bus stand"]
    },
    {
        "name": "Kariyampalayam & Vadavalli (Annur), Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.250000",
        "longitude": "77.120000",
        "keywords": ["kariyampalayam", "காரியம்பாளையம்", "vadavalli annur", "வடவள்ளி அன்னூர்"]
    },
    {
        "name": "Kuppepalayam & Kattampatty, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.220000",
        "longitude": "77.100000",
        "keywords": ["kuppepalayam", "குப்பப்பாளையம்", "kattampatty", "kattampatti", "காட்டம்பட்டி"]
    },
    {
        "name": "Kunnathur & Masagoundenpalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.260000",
        "longitude": "77.140000",
        "keywords": ["kunnathur annur", "குன்னத்தூர்", "masagoundenpalayam", "மாசகவுண்டன்பாளையம்"]
    },
    {
        "name": "Pachapalayam (Annur) & Naranapuram, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.210000",
        "longitude": "77.120000",
        "keywords": ["pachapalayam annur", "பச்சாபாளையம் அன்னூர்", "naranapuram", "நாரணாபுரம்"]
    },
    {
        "name": "Karegoundenpalayam & Bogalur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.230000",
        "longitude": "77.080000",
        "keywords": ["karegoundenpalayam", "காரேகவுண்டன்பாளையம்", "bogalur", "போகலூர்"]
    },
    {
        "name": "Odderpalayam & Kuppanur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.200000",
        "longitude": "77.110000",
        "keywords": ["odderpalayam", "ஒட்டர் பாளையம் அன்னூர்", "kuppanur", "குப்பனூர்"]
    },
    {
        "name": "Akkari Sengapally & Kanuvakarai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.240000",
        "longitude": "77.170000",
        "keywords": ["akkari sengapally", "அக்கரை செங்கப்பள்ளி", "sengapally", "kanuvakarai", "கணுவாக்கரை"]
    },
    {
        "name": "Aambothi & Vadakkalur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.220000",
        "longitude": "77.160000",
        "keywords": ["aambothi", "ஆம்போதி", "vadakkalur", "வடவக்கலூர்", "vadalur"]
    },
    {
        "name": "Annur Mettupalayam, Pasoor & Allapalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.250000",
        "longitude": "77.070000",
        "keywords": ["annur mettupalayam", "அன்னூர் மேட்டுப்பாளையம்", "pasoor", "pasur annur", "பாசூர்", "allapalayam", "அல்லப்பாளையம்"]
    },
    {
        "name": "Kanjampally & Vellamadai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.180000",
        "longitude": "77.050000",
        "keywords": ["kanjampally", "காஞ்சாம்பள்ளி", "vellamadai", "வெள்ளமடை"]
    },
    {
        "name": "Agraharasamakulam, Kondayampalayam & Sarkarsamakulam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.120000",
        "longitude": "77.020000",
        "keywords": ["agraharasamakulam", "அக்ரஹார சாமக்குளம்", "kondayampalayam", "கொண்டையம்பாளையம்", "sarkarsamakulam", "சர்க்கார் சாமக்குளம்", "kovilpalayam", "கோவில்பாளையம்"]
    },
    {
        "name": "Kallipalayam, Vellanaipatty, Keeranatham & Idigarai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.110000",
        "longitude": "77.000000",
        "keywords": ["kallipalayam", "கள்ளிப்பாளையம்", "vellanaipatty", "வெள்ளனைப்பட்டி", "keeranatham", "கீரநத்தம்", "idigarai", "இடிகரை", "chil sez keeranatham"]
    },

    # --- POLLACHI, KINATHUKADAVU, VALPARAI & ANAIMALAI TALUKS ---
    {
        "name": "Pollachi Town & Mahalingapuram, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.660000",
        "longitude": "77.010000",
        "keywords": ["pollachi", "பொள்ளாச்சி", "mahalingapuram pollachi", "மஹாலிங்கபுரம்", "achippatti", "unjavelampatti", "vadakkipalayam pollachi", "gomangalam", "samathur", "zamin uthukuli"]
    },
    {
        "name": "Kinathukadavu & Negamam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.820000",
        "longitude": "77.020000",
        "keywords": ["kinathukadavu", "கிணத்துக்கடவு", "negamam", "நெகமம்", "solavampalayam", "thamaraikulam"]
    },
    {
        "name": "Anaimalai & Sethumadai, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.583300",
        "longitude": "76.933300",
        "keywords": ["anaimalai", "ஆனைமலை", "anainamalai masani amman", "sethumadai", "topslip", "kottur pollachi", "vettaikaranpudur", "kambalapatti", "somandurai chittur"]
    },
    {
        "name": "Valparai & Sholayar Dam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.320000",
        "longitude": "76.955000",
        "keywords": ["valparai", "வால்பாறை", "sholayar dam", "சோலையார் அணை", "mudis", "stanmore", "rotikadavu", "waterfalls estate valparai"]
    },
    {
        "name": "Aliyar Dam & Monkey Falls, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.485000",
        "longitude": "76.972000",
        "keywords": ["aliyar", "ஆழியார்", "aliyar dam", "ஆழியார் அணை", "monkey falls", "குரங்கு அருவி", "temple of consciousness aliyar", "navamalai"]
    },

    # --- COIMBATORE SOUTH / CENTRAL URBAN ZONES ---
    {
        "name": "Gandhipuram, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.016800",
        "longitude": "76.967000",
        "keywords": ["gandhipuram", "காந்திபுரம்", "gandhipuram bus stand", "gandhipuram central", "cross cut road", "100 feet road", "seventh street gandhipuram"]
    },
    {
        "name": "RS Puram & Race Course, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.008321",
        "longitude": "76.949056",
        "keywords": ["rs puram", "r s puram", "rspuram", "ஆர் எஸ் புரம்", "db road", "race course coimbatore", "ரேஸ் கோர்ஸ்", "red fields", "collector office coimbatore"]
    },
    {
        "name": "Peelamedu & SITRA, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.026110",
        "longitude": "77.008240",
        "keywords": ["peelamedu", "பீளமேடு", "sitra", "சித்ரா", "coimbatore airport", "psg tech", "hopes college", "ஹோப்ஸ்", "tidel park coimbatore"]
    },
    {
        "name": "Ukkadam & Town Hall, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.988220",
        "longitude": "76.960240",
        "keywords": ["ukkadam", "உக்கடம்", "ukkadam bus stand", "town hall coimbatore", "டவுன் ஹால்", "oppanakara street", "big bazaar street", "karumbukadai", "athupalam"]
    },
    {
        "name": "Singanallur, Ramanathapuram & Sungam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.998400",
        "longitude": "77.025600",
        "keywords": ["singanallur", "சிங்காநல்லூர்", "ramanathapuram coimbatore", "ராமநாதபுரம் கோவை", "sungam", "சுங்கம்", "80 feet road ramanathapuram"]
    },
    {
        "name": "Pappanaickenpalayam, Sowripalayam & Ondipudur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.995000",
        "longitude": "77.045000",
        "keywords": ["pappanaickenpalayam", "pn palayam coimbatore", "பாப்பநாயக்கன்பாளையம்", "sowripalayam", "சௌரிபாளையம்", "ondipudur", "ஒண்டிப்புதூர்", "masakalipalayam"]
    },
    {
        "name": "Coimbatore Central, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.016800",
        "longitude": "76.955800",
        "keywords": ["coimbatore", "kovai", "கோயம்புத்தூர்", "கோவை", "coimbatore junction", "coimbatore north", "coimbatore south", "coimbatore corporation"]
    },



    # --------------------------------------------------------------------------
    # 2. CHENNAI DISTRICT (சென்னை)
    # --------------------------------------------------------------------------
    {
        "name": "T Nagar, Chennai District",
        "district": "Chennai",
        "latitude": "13.041800",
        "longitude": "80.234100",
        "keywords": ["t nagar", "t.nagar", "தி நகர்", "தி.நகர்", "தியாகராய நகர்", "panagal park", "பாண்டி பஜார்", "pondibazaar", "pondy bazaar"]
    },
    {
        "name": "Anna Nagar, Chennai District",
        "district": "Chennai",
        "latitude": "13.085000",
        "longitude": "80.210100",
        "keywords": ["anna nagar", "அண்ணா நகர்", "anna nagar tower", "shanthi colony"]
    },
    {
        "name": "Guindy, Chennai District",
        "district": "Chennai",
        "latitude": "13.006700",
        "longitude": "80.202500",
        "keywords": ["guindy", "கிண்டி", "kathipara", "கத்திப்பாரா", "guindy industrial estate"]
    },
    {
        "name": "Velachery, Chennai District",
        "district": "Chennai",
        "latitude": "12.981500",
        "longitude": "80.218000",
        "keywords": ["velachery", "வேளச்சேரி", "vijaya nagar velachery"]
    },
    {
        "name": "Mylapore, Chennai District",
        "district": "Chennai",
        "latitude": "13.036800",
        "longitude": "80.267600",
        "keywords": ["mylapore", "மயிலாப்பூர்", "mandaveli", "மந்தைவெளி", "luz corner"]
    },
    {
        "name": "Adyar, Chennai District",
        "district": "Chennai",
        "latitude": "13.001200",
        "longitude": "80.256500",
        "keywords": ["adyar", "அடையாறு", "besant nagar", "பெசன்ட் நகர்", "thiruvanmiyur", "திருவான்மியூர்"]
    },
    {
        "name": "Porur, Chennai District",
        "district": "Chennai",
        "latitude": "13.038200",
        "longitude": "80.156500",
        "keywords": ["porur", "போரூர்", "ramapuram", "ராமாபுரம்", "valasaravakkam", "வலசரவாக்கம்"]
    },
    {
        "name": "Chennai Central, Chennai District",
        "district": "Chennai",
        "latitude": "13.082700",
        "longitude": "80.270700",
        "keywords": ["chennai", "madras", "சென்னை", "மெட்ராஸ்", "egmore", "எழும்பூர்", "royapettah", "ராயப்பேட்டை", "kilpauk", "கீழ்ப்பாக்கம்", "perambur", "பெரம்பூர்", "nungambakkam", "நுங்கம்பாக்கம்", "saidapet", "சைதாப்பேட்டை", "vadapalani", "வடபழனி", "kodambakkam", "கோடம்பாக்கம்", "ambattur", "அம்பத்தூர்", "kolathur", "கொளத்தூர்", "madhavaram", "மாதவரம்", "triplicane", "திருவல்லிக்கேணி", "george town", "washermanpet", "வண்ணாரப்பேட்டை"]
    },

    # --------------------------------------------------------------------------
    # 3. CHENGALPATTU DISTRICT (செங்கல்பட்டு)
    # --------------------------------------------------------------------------
    {
        "name": "Tambaram, Chengalpattu District",
        "district": "Chengalpattu",
        "latitude": "12.924900",
        "longitude": "80.100000",
        "keywords": ["tambaram", "தாம்பரம்", "chromepet", "குரோம்பேட்டை", "pallavaram", "பல்லாவரம்", "vandalur", "வண்டலூர்", "perungalathur", "பெருங்களத்தூர்"]
    },
    {
        "name": "Mahabalipuram, Chengalpattu District",
        "district": "Chengalpattu",
        "latitude": "12.626900",
        "longitude": "80.192700",
        "keywords": ["mahabalipuram", "mamallapuram", "மகாபலிபுரம்", "மாமல்லபுரம்", "thiruporur", "திருப்போரூர்", "kelambakkam", "கேளம்பாக்கம்", "omr navalur", "siruseri", "சிறுசேரி"]
    },
    {
        "name": "Chengalpattu Central, Chengalpattu District",
        "district": "Chengalpattu",
        "latitude": "12.681900",
        "longitude": "79.988800",
        "keywords": ["chengalpattu", "செங்கல்பட்டு", "maraimalai nagar", "மறைமலை நகர்", "guduvanchery", "கூடுவாஞ்சேரி", "maduranthakam", "மதுராந்தகம்", "cheyyur", "செய்யூர்"]
    },

    # --------------------------------------------------------------------------
    # 4. TIRUVALLUR DISTRICT (திருவள்ளூர்)
    # --------------------------------------------------------------------------
    {
        "name": "Avadi, Tiruvallur District",
        "district": "Tiruvallur",
        "latitude": "13.114700",
        "longitude": "80.101800",
        "keywords": ["avadi", "ஆவடி", "poonamallee", "பூந்தமல்லி", "pattabiram", "பட்டாபிராம்"]
    },
    {
        "name": "Tiruvallur Central, Tiruvallur District",
        "district": "Tiruvallur",
        "latitude": "13.143200",
        "longitude": "79.907900",
        "keywords": ["tiruvallur", "thiruvallur", "திருவள்ளூர்", "ponneri", "பொன்னேரி", "gummidipoondi", "கும்மிடிப்பூண்டி", "tiruttani", "திருத்தணி", "minjur", "மீஞ்சூர்", "red hills", "ரெட்ஹில்ஸ்"]
    },

    # --------------------------------------------------------------------------
    # 5. MADURAI DISTRICT (மதுரை)
    # --------------------------------------------------------------------------
    {
        "name": "Mattuthavani, Madurai District",
        "district": "Madurai",
        "latitude": "9.948800",
        "longitude": "78.156900",
        "keywords": ["mattuthavani", "மாட்டுத்தாவணி", "mattuthavani bus stand"]
    },
    {
        "name": "Goripalayam, Madurai District",
        "district": "Madurai",
        "latitude": "9.932800",
        "longitude": "78.130500",
        "keywords": ["goripalayam", "கோரிப்பாளையம்", "simmakkal", "சிம்மக்கல்", "meenakshi amman temple", "மீனாட்சி அம்மன் கோவில்"]
    },
    {
        "name": "Thiruparankundram, Madurai District",
        "district": "Madurai",
        "latitude": "9.878800",
        "longitude": "78.072500",
        "keywords": ["thiruparankundram", "திருப்பரங்குன்றம்", "tirumangalam", "திருமங்கலம்", "melur", "மேலூர்", "usilampatti", "உசிலம்பட்டி", "vadipatti", "வாடிப்பட்டி", "sholavandan", "சோழவந்தான்", "alanganallur", "அலங்காநல்லூர்"]
    },
    {
        "name": "Madurai Central, Madurai District",
        "district": "Madurai",
        "latitude": "9.925200",
        "longitude": "78.119800",
        "keywords": ["madurai", "மதுரை", "periyar bus stand madurai", "பெரியார் பஸ் ஸ்டாண்ட்", "anna nagar madurai", "அண்ணா நகர் மதுரை", "kk nagar madurai", "கே கே நகர் மதுரை"]
    },

    # --------------------------------------------------------------------------
    # 6. TIRUCHIRAPPALLI DISTRICT (திருச்சிராப்பள்ளி)
    # --------------------------------------------------------------------------
    {
        "name": "Srirangam, Tiruchirappalli District",
        "district": "Tiruchirappalli",
        "latitude": "10.862500",
        "longitude": "78.694200",
        "keywords": ["srirangam", "ஸ்ரீரங்கம்", "ரங்கநாதர் கோவில்", "thiruvanaikaval", "திருவானைக்காவல்"]
    },
    {
        "name": "Thillai Nagar, Tiruchirappalli District",
        "district": "Tiruchirappalli",
        "latitude": "10.824200",
        "longitude": "78.685300",
        "keywords": ["thillai nagar", "தில்லை நகர்", "cantonment trichy", "ponmalai", "பொன்மலை", "golden rock", "thiruverumbur", "திருவெறும்பூர்", "tiruverumbur", "nit trichy", "துவாக்குடி", "thuvakudi"]
    },
    {
        "name": "Tiruchirappalli (Trichy) Central, Tiruchirappalli District",
        "district": "Tiruchirappalli",
        "latitude": "10.790500",
        "longitude": "78.704700",
        "keywords": ["trichy", "tiruchirappalli", "திருச்சி", "திருச்சிராப்பள்ளி", "lalgudi", "லால்குடி", "manapparai", "மணப்பாறை", "musiri", "முசிறி", "thuraiyur", "துறையூர்", "manachanallur", "மண்ணச்சநல்லூர்"]
    },

    # --------------------------------------------------------------------------
    # 7. SALEM DISTRICT (சேலம்)
    # --------------------------------------------------------------------------
    {
        "name": "Mettur, Salem District",
        "district": "Salem",
        "latitude": "11.796700",
        "longitude": "77.801100",
        "keywords": ["mettur", "மேட்டூர்", "mettur dam", "மேட்டூர் அணை"]
    },
    {
        "name": "Attur, Salem District",
        "district": "Salem",
        "latitude": "11.595600",
        "longitude": "78.601900",
        "keywords": ["attur", "ஆத்தூர்", "athoor", "vazhapadi", "வாழப்பாடி", "gangavalli", "கங்கவல்லி"]
    },
    {
        "name": "Salem Central, Salem District",
        "district": "Salem",
        "latitude": "11.664300",
        "longitude": "78.146000",
        "keywords": ["salem", "சேலம்", "salem junction", "yercaud", "ஏற்காடு", "omalur", "ஓமலூர்", "edappadi", "எடப்பாடி", "sankagiri", "சங்ககிரி", "tharamangalam", "தாரமங்கலம்", "jalakandapuram", "ஜலகண்டாபுரம்", "four roads salem", "suramangalam"]
    },

    # --------------------------------------------------------------------------
    # 8. THIRUVARUR DISTRICT (திருவாரூர்)
    # --------------------------------------------------------------------------
    {
        "name": "Mannargudi, Thiruvarur District",
        "district": "Thiruvarur",
        "latitude": "10.665300",
        "longitude": "79.447500",
        "keywords": ["mannargudi", "மன்னார்குடி", "ராஜகோபாலசுவாமி கோவில்", "mannargudi town"]
    },
    {
        "name": "Thiruthuraipoondi, Thiruvarur District",
        "district": "Thiruvarur",
        "latitude": "10.533300",
        "longitude": "79.650000",
        "keywords": ["thiruthuraipoondi", "திருத்துறைப்பூண்டி", "muthupet", "முத்துப்பேட்டை"]
    },
    {
        "name": "Thiruvarur Central, Thiruvarur District",
        "district": "Thiruvarur",
        "latitude": "10.772500",
        "longitude": "79.636500",
        "keywords": ["thiruvarur", "tiruvarur", "திருவாரூர்", "nannilam", "நன்னிலம்", "kodavasal", "குடவாசல்", "valangaiman", "வலங்கைமான்", "needamangalam", "நீடாமங்கலம்", "koothanallur", "கூத்தநல்லூர்", "kamalalayam", "கமலாலயம்"]
    },

    # --------------------------------------------------------------------------
    # 9. THANJAVUR DISTRICT (தஞ்சாவூர்)
    # --------------------------------------------------------------------------
    {
        "name": "Kumbakonam, Thanjavur District",
        "district": "Thanjavur",
        "latitude": "10.960200",
        "longitude": "79.384500",
        "keywords": ["kumbakonam", "கும்பகோணம்", "mahamaham tank", "மகாமகம்", "swamimalai", "சுவாமிமலை", "thiruvidaimarudur", "திருவிடைமருதூர்", "papanasam", "பாபநாசம்"]
    },
    {
        "name": "Pattukkottai, Thanjavur District",
        "district": "Thanjavur",
        "latitude": "10.428300",
        "longitude": "79.317500",
        "keywords": ["pattukkottai", "பட்டுக்கோட்டை", "peravurani", "பேராவூரணி", "orathanadu", "ஒரத்தநாடு"]
    },
    {
        "name": "Thanjavur Central, Thanjavur District",
        "district": "Thanjavur",
        "latitude": "10.787000",
        "longitude": "79.137800",
        "keywords": ["thanjavur", "tanjore", "தஞ்சாவூர்", "தஞ்சை", "brihadeeswarar temple", "பெரிய கோவில்", "thiruvaiyaru", "திருவையாறு", "budalur", "பூதலூர்"]
    },

    # --------------------------------------------------------------------------
    # 10. ERODE DISTRICT (ஈரோடு)
    # --------------------------------------------------------------------------
    {
        "name": "Gobichettipalayam, Erode District",
        "district": "Erode",
        "latitude": "11.454200",
        "longitude": "77.437500",
        "keywords": ["gobichettipalayam", "gobi", "கோபிசெட்டிபாளையம்", "கோபி", "sathyamangalam", "சத்தியமங்கலம்", "bhavanisagar", "பவானிசாகர்"]
    },
    {
        "name": "Bhavani, Erode District",
        "district": "Erode",
        "latitude": "11.450000",
        "longitude": "77.683300",
        "keywords": ["bhavani", "பவானி", "sangameshwarar", "அந்தியூர்", "anthiyur", "chennimalai", "சென்னிமலை"]
    },
    {
        "name": "Erode Central, Erode District",
        "district": "Erode",
        "latitude": "11.341000",
        "longitude": "77.717200",
        "keywords": ["erode", "ஈரோடு", "perundurai", "பெருந்துறை", "modakkurichi", "மொடக்குறிச்சி", "kodumudi", "கொடுமுடி", "chithode", "சித்தோடு"]
    },

    # --------------------------------------------------------------------------
    # 11. TIRUPPUR DISTRICT (திருப்பூர்)
    # --------------------------------------------------------------------------
    {
        "name": "Avinashi, Tiruppur District",
        "district": "Tiruppur",
        "latitude": "11.193100",
        "longitude": "77.268900",
        "keywords": ["avinashi", "அவிநாசி", "அவினாசி", "palladam", "பல்லடம்"]
    },
    {
        "name": "Dharapuram, Tiruppur District",
        "district": "Tiruppur",
        "latitude": "10.730000",
        "longitude": "77.530000",
        "keywords": ["dharapuram", "தாராபுரம்", "kangeyam", "காங்கேயம்", "udumalpet", "உடுமலைப்பேட்டை", "udumalaipettai", "madathukulam", "மடத்துக்குளம்"]
    },
    {
        "name": "Tiruppur Central, Tiruppur District",
        "district": "Tiruppur",
        "latitude": "11.108500",
        "longitude": "77.341100",
        "keywords": ["tiruppur", "tirupur", "திருப்பூர்", "uthukuli", "ஊத்துக்குளி", "kumaran road", "new bus stand tiruppur"]
    },

    # --------------------------------------------------------------------------
    # 12. DINDIGUL DISTRICT (திண்டுக்கல்)
    # --------------------------------------------------------------------------
    {
        "name": "Palani, Dindigul District",
        "district": "Dindigul",
        "latitude": "10.450000",
        "longitude": "77.516700",
        "keywords": ["palani", "பழனி", "palani temple", "oddanchatram", "ஒட்டன்சத்திரம்"]
    },
    {
        "name": "Kodaikanal, Dindigul District",
        "district": "Dindigul",
        "latitude": "10.238100",
        "longitude": "77.489200",
        "keywords": ["kodaikanal", "கொடைக்கானல்", "kodai", "கொடை"]
    },
    {
        "name": "Dindigul Central, Dindigul District",
        "district": "Dindigul",
        "latitude": "10.367300",
        "longitude": "77.980300",
        "keywords": ["dindigul", "திண்டுக்கல்", "nilakottai", "நிலக்கோட்டை", "natham", "நத்தம்", "vedasandur", "வேடசந்தூர்", "batlagundu", "வத்தலகுண்டு", "gujiliamparai", "குஜிலியம்பாறை"]
    },

    # --------------------------------------------------------------------------
    # 13. TIRUNELVELI DISTRICT (திருநெல்வேலி)
    # --------------------------------------------------------------------------
    {
        "name": "Tirunelveli Junction & Town, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.728000",
        "longitude": "77.698000",
        "keywords": ["tirunelveli town", "திருநெல்வேலி டவுன்", "tirunelveli junction", "திருநெல்வேலி ஜங்ஷன்", "nellaiappar temple", "நெல்லையப்பர் கோவில்", "swami nellaiappar sannadhi", "swami sannathi", "town car street", "rathaveethi", "nainarkulam", "நயினார்குளம்", "sindhupoondurai", "சிந்துபூந்துறை", "veeraraghavapuram", "வீரராகவபுரம்", "madurai road junction", "iruttukadai halwa", "இருட்டுக்கடை அல்வா"]
    },
    {
        "name": "Palayamkottai, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.718300",
        "longitude": "77.746100",
        "keywords": ["palayamkottai", "பாளை", "பாளையங்கோட்டை", "oxford of south india", "st xaviers palayamkottai", "sarah tucker", "palayamkottai market", "palayamkottai bus stand", "south bazaar palayamkottai", "murugankurichi", "முருகன்குறிச்சி"]
    },
    {
        "name": "Melapalayam, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.705000",
        "longitude": "77.725000",
        "keywords": ["melapalayam", "மேலப்பாளையம்", "melapalayam cattle market", "hameempuram", "ஹமீம்புரம்", "asad nagar melapalayam", "al ameen street", "melapalayam railway station", "kurichi melapalayam"]
    },
    {
        "name": "Thachanallur, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.750000",
        "longitude": "77.720000",
        "keywords": ["thachanallur", "தச்சநல்லூர்", "thachanallur bypass", "ramayanpatti", "ராமையன்பட்டி", "chathiram pudukulam", "palavoor thachanallur"]
    },
    {
        "name": "Vannarpettai & Kokkirakulam, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.725000",
        "longitude": "77.728000",
        "keywords": ["vannarpettai", "வண்ணாரப்பேட்டை", "vannarpet", "kokkirakulam", "கொக்கிரகுளம்", "nellai collectorate", "collector office tirunelveli", "sulochana mudaliar bridge", "tamirabarani river bridge"]
    },
    {
        "name": "Pettai, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.720000",
        "longitude": "77.665000",
        "keywords": ["pettai tirunelveli", "பேட்டை திருநெல்வேலி", "pettai industrial estate", "sidco pettai", "pettai bazaar", "kailasapuram pettai", "cheranmahadevi road pettai"]
    },
    {
        "name": "Samathanapuram, Maharaja Nagar & Perumalpuram, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.710000",
        "longitude": "77.755000",
        "keywords": ["samathanapuram", "சமாதானபுரம்", "maharaja nagar", "மகாராஜா நகர்", "perumalpuram", "பெருமாள்புரம்", "vasantha nagar nellai", "வசந்த நகர்"]
    },
    {
        "name": "Rahmath Nagar, Shanthi Nagar & High Ground, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.705000",
        "longitude": "77.760000",
        "keywords": ["rahmath nagar", "ரஹ்மத் நகர்", "shanthi nagar tirunelveli", "சாந்தி நகர்", "high ground tirunelveli", "ஹைகிரவுண்ட்", "nellai medical college", "government medical college hospital tirunelveli", "tvmch"]
    },
    {
        "name": "KTC Nagar, NGO Colony & Reddiarpatti, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.690000",
        "longitude": "77.750000",
        "keywords": ["ktc nagar", "கேடிசி நகர்", "ngo colony tirunelveli", "என்ஜிஓ காலனி", "reddiarpatti", "ரெட்டியார்பட்டி", "vm chatram", "வி எம் சத்திரம்", "anbu nagar nellai", "kulavanigarpuram", "குலவணிகர்புரம்", "kulavanigarpuram railway gate"]
    },
    {
        "name": "Ambasamudram & Urkad, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.705000",
        "longitude": "77.458900",
        "keywords": ["ambasamudram", "அம்பாசமுத்திரம்", "ambai", "அம்பை", "urkad", "ஊர்க்காடு", "brammadesam", "பிரம்மதேசம்", "mannarkovil", "மன்னர்கோவில்", "vellanguli", "வெள்ளாங்குளி"]
    },
    {
        "name": "Vikramasingapuram (VK Puram) & Sivanthipuram, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.670000",
        "longitude": "77.420000",
        "keywords": ["vikramasingapuram", "விக்கிரமசிங்கபுரம்", "vk puram", "விகே புரம்", "sivanthipuram", "சிவந்திபுரம்", "madura coats vk puram", "therku pappankulam", "தெற்கு பாப்பன்குளம்"]
    },
    {
        "name": "Papanasam & Agasthiyar Falls, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.700000",
        "longitude": "77.370000",
        "keywords": ["papanasam nellai", "பாபநாசம் நெல்லை", "agasthiyar falls", "அகத்தியர் அருவி", "papanasam dam", "பாபநாசம் அணை", "kalyana theertham", "கல்யாண தீர்த்தம்", "lower camp papanasam", "agasthiyar temple"]
    },
    {
        "name": "Manimuthar & Manimuthar Dam, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.625000",
        "longitude": "77.410000",
        "keywords": ["manimuthar", "மணிமுத்தாறு", "manimuthar dam", "மணிமுத்தாறு அணை", "manimuthar waterfalls", "manjolai", "மாஞ்சோலை", "kakkachi", "காக்காச்சி", "nalumukku", "நாலுமுக்கு", "oothu", "ஊத்து", "singampatti zamin", "சிங்கம்பட்டி ஜமீன்"]
    },
    {
        "name": "Kallidaikurichi, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.690000",
        "longitude": "77.460000",
        "keywords": ["kallidaikurichi", "கல்லிடைக்குறிச்சி", "kallidaikurchi", "kallidaikurichi appalam", "thamirabarani kallidaikurichi", "bhoothanatha swamy temple"]
    },
    {
        "name": "Alwarkurichi & Pottalpudur, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.780000",
        "longitude": "77.400000",
        "keywords": ["alwarkurichi", "ஆழ்வார்குறிச்சி", "pottalpudur", "பொட்டல்புதூர்", "pottalpudur dargah", "பொட்டல்புதூர் தர்கா", "ravanasamudram", "ரவணசமுத்திரம்", "sivasailam", "சிவசைலம்", "sivasailam temple", "சிவசைலம் கோவில்"]
    },
    {
        "name": "Mukkudal & Pappakudi, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.730000",
        "longitude": "77.520000",
        "keywords": ["mukkudal", "முக்கூடல்", "pappakudi", "பாப்பாக்குடி", "karisalpatti", "கரிசல்பட்டி", "vagaikulam", "வாகைகுளம்", "ariyanayagipuram", "அரியநாயகிபுரம்", "mukkudal beedi"]
    },
    {
        "name": "Kadayam & Singampatti, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.810000",
        "longitude": "77.380000",
        "keywords": ["kadayam", "கடையம்", "kizha kadayam", "கீழக்கடையம்", "mela kadayam", "மேலக்கடையம்", "singampatti", "சிங்கம்பட்டி", "ayasingampatti", "அய்சிங்கம்பட்டி", "bharathiyar kadayam"]
    },
    {
        "name": "Cheranmahadevi, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.680000",
        "longitude": "77.560000",
        "keywords": ["cheranmahadevi", "சேரன்மகாதேவி", "cheranmadevi", "சேரன்மாதேவி", "cheranmahadevi sub division", "ramaswamy temple cheranmahadevi"]
    },
    {
        "name": "Veeravanallur, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.685000",
        "longitude": "77.510000",
        "keywords": ["veeravanallur", "வீரவநல்லூர்", "sundarasowbagyam", "veeravanallur handloom", "bharathanagar"]
    },
    {
        "name": "Pathamadai (Pattamadai), Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.665000",
        "longitude": "77.585000",
        "keywords": ["pathamadai", "pattamadai", "பட்டமடை", "பத்தமடை", "pattamadai pai", "பத்தமடை பாய்", "swami sivananda pathamadai", "pattamadai mat"]
    },
    {
        "name": "Melaseval & Gopalasamudram, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.670000",
        "longitude": "77.620000",
        "keywords": ["melaseval", "மேலச்செவல்", "gopalasamudram", "கோபாலசமுத்திரம்", "karukurichi", "கருக்குறிச்சி", "tharuvai", "தருவை", "melapattam", "மேலப்பட்டம்", "kuniyur", "குனியூர்", "kodaganallur", "கோடகநல்லூர்"]
    },
    {
        "name": "Nanguneri & Totakudi, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.490000",
        "longitude": "77.660000",
        "keywords": ["nanguneri", "நாங்குநேரி", "vanamamalai temple", "வானமாமலை பெருமாள் கோவில்", "totakudi", "தோட்டாக்குடி", "paruthipadu", "பருத்திப்பாடு", "nanguneri tollgate", "nanguneri sez"]
    },
    {
        "name": "Kalakkad & Singikulam, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.510000",
        "longitude": "77.550000",
        "keywords": ["kalakkad", "களக்காடு", "kalakad", "kmtr sanctuary", "kalakkad mundanthurai tiger reserve", "singikulam", "சிங்கிகுளம்", "padmaneri", "பத்மநேரி", "devanallur", "தேவனல்லூர்"]
    },
    {
        "name": "Eruvadi & Thirukkurungudi, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.440000",
        "longitude": "77.560000",
        "keywords": ["eruvadi", "ஏர்வாடி திருநெல்வேலி", "eruvadi nellai", "thirukkurungudi", "திருக்குறுங்குடி", "nambi temple", "நம்பி கோவில்", "thirukurungudi", "nambikoil"]
    },
    {
        "name": "Munanjipatti, Dohnavur & Ittamozhi, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.460000",
        "longitude": "77.680000",
        "keywords": ["munanjipatti", "முனைஞ்சிபட்டி", "dohnavur", "தோணாவூர்", "dohnavur fellowship", "ittamozhi", "இட்டமொழி", "suviseshapuram", "சுவிசேஷபுரம்", "karungulam nellai"]
    },
    {
        "name": "Vijayanarayanam & Moondradaippu, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.420000",
        "longitude": "77.770000",
        "keywords": ["vijayanarayanam", "விஜயநாராயணம்", "ins kattabomman", "moondradaippu", "மூன்றடைப்பு", "dalapathisamudram", "தளபதிசமுத்திரம்", "moondradaippu checkpost"]
    },
    {
        "name": "Vallioor, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.380000",
        "longitude": "77.615000",
        "keywords": ["vallioor", "valliyur", "வள்ளியூர்", "vallioor murugan temple", "வள்ளியூர் முருகன் கோவில்", "vallioor new bus stand", "vallioor bypass"]
    },
    {
        "name": "Radhapuram, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.310000",
        "longitude": "77.680000",
        "keywords": ["radhapuram", "ராதாபுரம்", "radhapuram taluk", "radhapuram police station", "kasthurirangapuram", "கஸ்தூரிரங்கபுரம்", "soundarapandiapuram", "சௌந்தரபாண்டியபுரம்"]
    },
    {
        "name": "Kudankulam (Koodankulam) & Idinthakarai, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.175000",
        "longitude": "77.710000",
        "keywords": ["kudankulam", "koodankulam", "கூடங்குளம்", "koodankulam nuclear power plant", "அணுமின் நிலையம் கூடங்குளம்", "idinthakarai", "இடிந்தகரை", "vijayapathi", "விஜயாபதி", "chettikulam", "செட்டிகுளம்"]
    },
    {
        "name": "Panagudi, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.320000",
        "longitude": "77.580000",
        "keywords": ["panagudi", "பனகுடி", "panagudi windmills", "பனங்குடி", "thalavaipuram nellai", "தாளவாய்புரம்", "panagudi police station"]
    },
    {
        "name": "Thisayanvilai & Uvari, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.330000",
        "longitude": "77.860000",
        "keywords": ["thisayanvilai", "திசையன்விளை", "uvari", "உவரி", "uvari suyambulingam temple", "சுயம்புலிங்க சுவாமி கோவில்", "uvari st antony church", "உவரி அந்தோணியார் கோவில்", "karaichuthu uvari", "கரைச்சுத்து உவரி", "appuvilai", "அப்புவிளை", "idaiyangudi", "இடையன்குடி"]
    },
    {
        "name": "Vadakkankulam, Pazhavoor & Kavalkinaru, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.270000",
        "longitude": "77.570000",
        "keywords": ["vadakkankulam", "வடக்கன்குளம்", "pazhavoor", "பழவூர்", "kavalkinaru", "காவல்கிணறு", "kavalkinaru junction", "levinjipuram", "லெவிஞ்சிபுரம்", "jacobpuram", "ஜேக்கப்புரம்"]
    },
    {
        "name": "Manur & Devarkulam, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.830000",
        "longitude": "77.650000",
        "keywords": ["manur", "மானூர்", "manur periyakulam", "மானூர் பெரியகுளம்", "devarkulam", "தேவர்குளம்", "alagiapandiapuram", "அழகியபாண்டியபுரம்", "sethurayanputhur", "சேதுராயன்புதூர்"]
    },
    {
        "name": "Gangaikondan & SIPCOT, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.860000",
        "longitude": "77.780000",
        "keywords": ["gangaikondan", "கங்கைகொண்டான்", "gangaikondan sipcot", "சிப்காட் கங்கைகொண்டான்", "gangaikondan deer sanctuary", "மான்கள் சரணாலயம் கங்கைகொண்டான்", "pallikottai", "பள்ளிக்கோட்டை"]
    },
    {
        "name": "Sankar Nagar, Thalaiyuthu & Suthamalli, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.790000",
        "longitude": "77.720000",
        "keywords": ["sankar nagar", "சங்கர் நகர்", "thalaiyuthu", "தாழையூத்து", "india cements sankar nagar", "suthamalli", "சுத்தமல்லி", "kondanagaram", "கொண்டாநகரம்"]
    },
    {
        "name": "Ukkirankottai & Vannikonendal, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.890000",
        "longitude": "77.610000",
        "keywords": ["ukkirankottai", "உக்கிரன்கோட்டை", "vannikonendal", "வன்னிக்கோனேந்தல்", "madhavakurichi", "மாதவக்குறிச்சி", "maruthakulam", "மருதகுளம்"]
    },
    {
        "name": "Tirunelveli Central, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.713900",
        "longitude": "77.756700",
        "keywords": ["tirunelveli", "nellai", "திருநெல்வேலி", "நெல்லை", "tirunelveli corporation", "நெல்லை மாநகராட்சி", "nellai district"]
    },


    # --------------------------------------------------------------------------
    # 14. TENKASI DISTRICT (தென்காசி)
    # --------------------------------------------------------------------------
    {
        "name": "Courtallam, Tenkasi District",
        "district": "Tenkasi",
        "latitude": "8.932800",
        "longitude": "77.273600",
        "keywords": ["courtallam", "kutralam", "குற்றாலம்", "குற்றால அருவி"]
    },
    {
        "name": "Sankarankovil, Tenkasi District",
        "district": "Tenkasi",
        "latitude": "9.172200",
        "longitude": "77.532200",
        "keywords": ["sankarankovil", "சங்கரன்கோவில்", "kadayanallur", "கடையநல்லூர்", "puliyangudi", "புளியங்குடி", "sivagiri", "சிவகிரி"]
    },
    {
        "name": "Tenkasi Central, Tenkasi District",
        "district": "Tenkasi",
        "latitude": "8.959400",
        "longitude": "77.314200",
        "keywords": ["tenkasi", "தென்காசி", "sengottai", "செங்கோட்டை", "alangulam", "ஆலங்குளம்", "thiruvengadam", "திருவேங்கடம்"]
    },

    # --------------------------------------------------------------------------
    # 15. THOOTHUKUDI DISTRICT (தூத்துக்குடி)
    # --------------------------------------------------------------------------
    {
        "name": "Tiruchendur, Thoothukudi District",
        "district": "Thoothukudi",
        "latitude": "8.496700",
        "longitude": "78.125600",
        "keywords": ["tiruchendur", "திருச்செந்தூர்", "tiruchendur murugan temple"]
    },
    {
        "name": "Kovilpatti, Thoothukudi District",
        "district": "Thoothukudi",
        "latitude": "9.173100",
        "longitude": "77.868900",
        "keywords": ["kovilpatti", "கோவில்பட்டி", "ettayapuram", "எட்டயபுரம்", "bharathiyar ninaivagam", "kayalpattinam", "காயல்பட்டினம்"]
    },
    {
        "name": "Thoothukudi Central, Thoothukudi District",
        "district": "Thoothukudi",
        "latitude": "8.764200",
        "longitude": "78.134800",
        "keywords": ["thoothukudi", "tuticorin", "தூத்துக்குடி", "vilathikulam", "விளாத்திகுளம்", "srivaikuntam", "ஸ்ரீவைகுண்டம்", "sathankulam", "சாத்தான்குளம்", "spic nagar"]
    },

    # --------------------------------------------------------------------------
    # 16. KANYAKUMARI DISTRICT (கன்னியாகுமரி)
    # --------------------------------------------------------------------------
    {
        "name": "Nagercoil, Kanyakumari District",
        "district": "Kanyakumari",
        "latitude": "8.183300",
        "longitude": "77.411900",
        "keywords": ["nagercoil", "நாகர்கோவில்", "vadasery", "வடசேரி", "kottar", "கோட்டாறு"]
    },
    {
        "name": "Kanyakumari Town, Kanyakumari District",
        "district": "Kanyakumari",
        "latitude": "8.088300",
        "longitude": "77.538500",
        "keywords": ["kanyakumari", "கன்னியாகுமரி", "vivekananda rock", "thiruvalluvar statue", "விவேகானந்தர் பாறை", "marthandam", "மார்த்தாண்டம்", "thuckalay", "தக்கலை", "padmanabhapuram", "பத்மநாபபுரம்", "colachel", "குளச்சல்", "kuzhithurai", "குழித்துறை"]
    },

    # --------------------------------------------------------------------------
    # 17. VELLORE DISTRICT (வேலூர்)
    # --------------------------------------------------------------------------
    {
        "name": "Katpadi, Vellore District",
        "district": "Vellore",
        "latitude": "12.980000",
        "longitude": "79.136400",
        "keywords": ["katpadi", "காட்பாடி", "vit vellore", "katpadi junction"]
    },
    {
        "name": "Vellore Central, Vellore District",
        "district": "Vellore",
        "latitude": "12.916500",
        "longitude": "79.132500",
        "keywords": ["vellore", "வேலூர்", "cmc vellore", "vellore fort", "gudiyatham", "குடியாத்தம்", "pernambut", "பேரணாம்பட்டு", "anaicut", "அணைக்கட்டு", "kaniyambadi", "கணியம்பாடி"]
    },

    # --------------------------------------------------------------------------
    # 18. RANIPET DISTRICT (ராணிப்பேட்டை)
    # --------------------------------------------------------------------------
    {
        "name": "Arakkonam, Ranipet District",
        "district": "Ranipet",
        "latitude": "13.080000",
        "longitude": "79.670000",
        "keywords": ["arakkonam", "அரக்கோணம்", "sholinghur", "சோளிங்கர்"]
    },
    {
        "name": "Ranipet Central, Ranipet District",
        "district": "Ranipet",
        "latitude": "12.927200",
        "longitude": "79.332500",
        "keywords": ["ranipet", "ராணிப்பேட்டை", "walajah", "வாலாஜா", "arcot", "ஆற்காடு", "nemili", "நெமிலி"]
    },

    # --------------------------------------------------------------------------
    # 19. TIRUPATHUR DISTRICT (திருப்பத்தூர்)
    # --------------------------------------------------------------------------
    {
        "name": "Ambur & Vaniyambadi, Tirupathur District",
        "district": "Tirupathur",
        "latitude": "12.790600",
        "longitude": "78.715300",
        "keywords": ["ambur", "ஆம்பூர்", "vaniyambadi", "வாணியம்பாடி", "yelagiri", "ஏலகிரி", "yelagiri hills"]
    },
    {
        "name": "Tirupathur Central, Tirupathur District",
        "district": "Tirupathur",
        "latitude": "12.495000",
        "longitude": "78.567800",
        "keywords": ["tirupathur", "thirupathur vellore", "திருப்பத்தூர்", "jolarpet", "ஜோலார்பேட்டை", "natrampalli", "நாட்ராம்பள்ளி"]
    },

    # --------------------------------------------------------------------------
    # 20. KRISHNAGIRI DISTRICT (கிருஷ்ணகிரி)
    # --------------------------------------------------------------------------
    {
        "name": "Hosur, Krishnagiri District",
        "district": "Krishnagiri",
        "latitude": "12.740900",
        "longitude": "77.825300",
        "keywords": ["hosur", "ஓசூர்", "hosur sipcot", "bagalur", "பாகலூர்", "shoolagiri", "சூளகிரி"]
    },
    {
        "name": "Krishnagiri Central, Krishnagiri District",
        "district": "Krishnagiri",
        "latitude": "12.518600",
        "longitude": "78.213800",
        "keywords": ["krishnagiri", "கிருஷ்ணகிரி", "denkanikottai", "தேன்கனிக்கோட்டை", "pochampalli", "போச்சம்பள்ளி", "uthangarai", "ஊத்தங்கரை", "bargur", "பர்கூர்"]
    },

    # --------------------------------------------------------------------------
    # 21. DHARMAPURI DISTRICT (தருமபுரி)
    # --------------------------------------------------------------------------
    {
        "name": "Hogenakkal, Dharmapuri District",
        "district": "Dharmapuri",
        "latitude": "12.118900",
        "longitude": "77.776100",
        "keywords": ["hogenakkal", "ஒகேனக்கல்", "hogenakkal falls", "pennagaram", "பெPennagaram", "பெண்ணாகரம்"]
    },
    {
        "name": "Dharmapuri Central, Dharmapuri District",
        "district": "Dharmapuri",
        "latitude": "12.121100",
        "longitude": "78.158200",
        "keywords": ["dharmapuri", "தருமபுரி", "தர்மபுரி", "harur", "அரூர்", "palacode", "பாலக்கோடு", "pappireddipatti", "பாப்பிரெட்டிப்பட்டி", "karimangalam", "காரிமங்கலம்", "nallampalli", "நல்லம்பள்ளி"]
    },

    # --------------------------------------------------------------------------
    # 22. KANCHIPURAM DISTRICT (காஞ்சிபுரம்)
    # --------------------------------------------------------------------------
    {
        "name": "Sriperumbudur, Kanchipuram District",
        "district": "Kanchipuram",
        "latitude": "12.966700",
        "longitude": "79.950000",
        "keywords": ["sriperumbudur", "ஸ்ரீபெரும்புதூர்", "sipcot sriperumbudur", "kundrathur", "குன்றத்தூர்"]
    },
    {
        "name": "Kanchipuram Central, Kanchipuram District",
        "district": "Kanchipuram",
        "latitude": "12.834200",
        "longitude": "79.703600",
        "keywords": ["kanchipuram", "காஞ்சிபுரம்", "காஞ்சி", "walajabad", "வாலாஜாபாத்", "uthiramerur", "உத்திரமேரூர்", "kamakshi amman temple"]
    },

    # --------------------------------------------------------------------------
    # 23. TIRUVANNAMALAI DISTRICT (திருவண்ணாமலை)
    # --------------------------------------------------------------------------
    {
        "name": "Arani & Cheyyar, Tiruvannamalai District",
        "district": "Tiruvannamalai",
        "latitude": "12.668300",
        "longitude": "79.283900",
        "keywords": ["arani", "ஆரணி", "cheyyar", "செய்யாறு", "polur", "போளூர்", "vandavasi", "வந்தவாசி"]
    },
    {
        "name": "Tiruvannamalai Central, Tiruvannamalai District",
        "district": "Tiruvannamalai",
        "latitude": "12.225300",
        "longitude": "79.074700",
        "keywords": ["tiruvannamalai", "thiruvannamalai", "திருவண்ணாமலை", "girivalam", "கிரிவலம்", "annamaliyar", "chengam", "செங்கம்", "kalasapakkam", "கலசப்பாக்கம்", "jawadhu hills", "ஜவ்வாது மலை"]
    },

    # --------------------------------------------------------------------------
    # 24. VILUPPURAM DISTRICT (விழுப்புரம்)
    # --------------------------------------------------------------------------
    {
        "name": "Gingee (Senji), Viluppuram District",
        "district": "Viluppuram",
        "latitude": "12.250000",
        "longitude": "79.416700",
        "keywords": ["gingee", "senji", "செஞ்சி", "gingee fort", "செஞ்சிக் கோட்டை", "tindivanam", "திண்டிவனம்"]
    },
    {
        "name": "Viluppuram Central, Viluppuram District",
        "district": "Viluppuram",
        "latitude": "11.940100",
        "longitude": "79.486100",
        "keywords": ["viluppuram", "villupuram", "விழுப்புரம்", "vanur", "வானூர்", "vikravandi", "விக்ரவாண்டி", "marakkanam", "மரக்காணம்"]
    },

    # --------------------------------------------------------------------------
    # 25. KALLAKURICHI DISTRICT (கள்ளக்குறிச்சி)
    # --------------------------------------------------------------------------
    {
        "name": "Tirukoilur & Ulundurpet, Kallakurichi District",
        "district": "Kallakurichi",
        "latitude": "11.960000",
        "longitude": "79.200000",
        "keywords": ["tirukoilur", "திருக்கோவிலூர்", "ulundurpet", "உளுந்தூர்பேட்டை", "sankarapuram", "சங்கராபுரம்"]
    },
    {
        "name": "Kallakurichi Central, Kallakurichi District",
        "district": "Kallakurichi",
        "latitude": "11.738300",
        "longitude": "78.963900",
        "keywords": ["kallakurichi", "கள்ளக்குறிச்சி", "chinnasalem", "சின்னசேலம்", "kalvarayan hills", "கல்வராயன் மலை"]
    },

    # --------------------------------------------------------------------------
    # 26. CUDDALORE DISTRICT (கடலூர்)
    # --------------------------------------------------------------------------
    {
        "name": "Chidambaram, Cuddalore District",
        "district": "Cuddalore",
        "latitude": "11.399200",
        "longitude": "79.693600",
        "keywords": ["chidambaram", "சிதம்பரம்", "thillai nataraja temple", "pitchavaram", "பிச்சாவரம்"]
    },
    {
        "name": "Neyveli & Vridhachalam, Cuddalore District",
        "district": "Cuddalore",
        "latitude": "11.599700",
        "longitude": "79.486100",
        "keywords": ["neyveli", "நெய்வேலி", "nlc india", "vridhachalam", "விருத்தாசலம்", "panruti", "பண்ருட்டி"]
    },
    {
        "name": "Cuddalore Central, Cuddalore District",
        "district": "Cuddalore",
        "latitude": "11.748000",
        "longitude": "79.771400",
        "keywords": ["cuddalore", "கடலூர்", "silver beach", "kurinjipadi", "குறிஞ்சிப்பாடி", "tittagudi", "திட்டக்குடி", "bhuvanagiri", "புவனகிரி", "kattumannarkoil", "காட்டுமன்னார்கோவில்"]
    },

    # --------------------------------------------------------------------------
    # 27. NAGAPATTINAM DISTRICT (நாகப்பட்டினம்)
    # --------------------------------------------------------------------------
    {
        "name": "Velankanni, Nagapattinam District",
        "district": "Nagapattinam",
        "latitude": "10.680000",
        "longitude": "79.850000",
        "keywords": ["velankanni", "வேளாங்கண்ணி", "velankanni church", "nagore", "நாகூர்", "nagore dargah"]
    },
    {
        "name": "Nagapattinam Central, Nagapattinam District",
        "district": "Nagapattinam",
        "latitude": "10.767200",
        "longitude": "79.844900",
        "keywords": ["nagapattinam", "நாகப்பட்டினம்", "vedaranyam", "வேதாரண்யம்", "kilvelur", "கீழ்வேளூர்", "thirukkuvalai", "திருக்குவளை"]
    },

    # --------------------------------------------------------------------------
    # 28. MAYILADUTHURAI DISTRICT (மயிலாடுதுறை)
    # --------------------------------------------------------------------------
    {
        "name": "Sirkazhi & Poompuhar, Mayiladuthurai District",
        "district": "Mayiladuthurai",
        "latitude": "11.233300",
        "longitude": "79.733300",
        "keywords": ["sirkazhi", "சீர்காழி", "poompuhar", "பூம்புகார்", "tharangambadi", "தரங்கம்பாடி", "tranquebar"]
    },
    {
        "name": "Mayiladuthurai Central, Mayiladuthurai District",
        "district": "Mayiladuthurai",
        "latitude": "11.107500",
        "longitude": "79.652400",
        "keywords": ["mayiladuthurai", "mayavaram", "மயிலாடுதுறை", "மாயவரம்", "kuthalam", "குத்தாலம்"]
    },

    # --------------------------------------------------------------------------
    # 29. ARIYALUR DISTRICT (அரியலூர்)
    # --------------------------------------------------------------------------
    {
        "name": "Jayankondam & Gangaikonda Cholapuram, Ariyalur District",
        "district": "Ariyalur",
        "latitude": "11.216700",
        "longitude": "79.366700",
        "keywords": ["jayankondam", "ஜெயங்கொண்டம்", "gangaikonda cholapuram", "கங்கைகொண்ட சோழபுரம்", "udayarpalayam", "உடையார்பாளையம்", "andimadam", "ஆண்டிமடம்"]
    },
    {
        "name": "Ariyalur Central, Ariyalur District",
        "district": "Ariyalur",
        "latitude": "11.140100",
        "longitude": "79.078600",
        "keywords": ["ariyalur", "அரியலூர்", "sendurai", "செந்துறை"]
    },

    # --------------------------------------------------------------------------
    # 30. PERAMBALUR DISTRICT (பெரம்பலூர்)
    # --------------------------------------------------------------------------
    {
        "name": "Perambalur Central, Perambalur District",
        "district": "Perambalur",
        "latitude": "11.234200",
        "longitude": "78.882000",
        "keywords": ["perambalur", "பெரம்பலூர்", "veppanthattai", "வேப்பந்தட்டை", "kunnam", "குன்னம்", "alathur perambalur", "ஆலத்தூர்"]
    },

    # --------------------------------------------------------------------------
    # 31. NAMAKKAL DISTRICT (நாமக்கல்)
    # --------------------------------------------------------------------------
    {
        "name": "Tiruchengode & Rasipuram, Namakkal District",
        "district": "Namakkal",
        "latitude": "11.380000",
        "longitude": "77.890000",
        "keywords": ["tiruchengode", "திருச்செங்கோடு", "rasipuram", "ராசிபுரம்", "kolli hills", "கொல்லிமலை", "komarapalayam", "குமாரபாளையம்"]
    },
    {
        "name": "Namakkal Central, Namakkal District",
        "district": "Namakkal",
        "latitude": "11.218900",
        "longitude": "78.167400",
        "keywords": ["namakkal", "நாமக்கல்", "paramathi velur", "பரமத்தி வேலூர்", "sendamangalam", "சேந்தமங்கலம்", "mohanur", "மோகனூர்", "namakkal anjaneyar"]
    },

    # --------------------------------------------------------------------------
    # 32. KARUR DISTRICT (கரூர்)
    # --------------------------------------------------------------------------
    {
        "name": "Kulithalai & Pugalur, Karur District",
        "district": "Karur",
        "latitude": "10.933300",
        "longitude": "78.416700",
        "keywords": ["kulithalai", "குளித்தலை", "pugalur", "புகழூர்", "aravakurichi", "அரவக்குறிச்சி", "pallapatti", "பள்ளபட்டி"]
    },
    {
        "name": "Karur Central, Karur District",
        "district": "Karur",
        "latitude": "10.960100",
        "longitude": "78.076600",
        "keywords": ["karur", "கரூர்", "krishnarayapuram", "கிருஷ்ணராயபுரம்", "mayanur", "மாயனூர்", "velur karur", "pasupatheeswarar"]
    },

    # --------------------------------------------------------------------------
    # 33. PUDUKKOTTAI DISTRICT (புதுக்கோட்டை)
    # --------------------------------------------------------------------------
    {
        "name": "Aranthangi & Viralimalai, Pudukkottai District",
        "district": "Pudukkottai",
        "latitude": "10.166700",
        "longitude": "78.983300",
        "keywords": ["aranthangi", "அறந்தாங்கி", "viralimalai", "விராலிமலை", "thirumayam", "திருமயம்", "chithannavasal", "சித்தன்னவாசல்"]
    },
    {
        "name": "Pudukkottai Central, Pudukkottai District",
        "district": "Pudukkottai",
        "latitude": "10.383300",
        "longitude": "78.816700",
        "keywords": ["pudukkottai", "புதுக்கோட்டை", "gandarvakottai", "கந்தர்வகோட்டை", "alangudi", "ஆலங்குடி", "ponnamaravathi", "பொன்னமராவதி", "avudaiyarkoil", "ஆவுடையார்கோவில்", "karambakkudi", "கறம்பக்குடி"]
    },

    # --------------------------------------------------------------------------
    # 34. SIVAGANGA DISTRICT (சிவகங்கை)
    # --------------------------------------------------------------------------
    {
        "name": "Karaikudi (Chettinad), Sivaganga District",
        "district": "Sivaganga",
        "latitude": "10.066700",
        "longitude": "78.783300",
        "keywords": ["karaikudi", "காரைக்குடி", "chettinad", "செட்டிநாடு", "devakottai", "தேவகோட்டை", "alikkudi", "alagappa university"]
    },
    {
        "name": "Sivaganga Central, Sivaganga District",
        "district": "Sivaganga",
        "latitude": "9.843300",
        "longitude": "78.480000",
        "keywords": ["sivaganga", "sivagangai", "சிவகங்கை", "manamadurai", "மானாமதுரை", "tiruppattur sivaganga", "திருப்பத்தூர் சிவகங்கை", "ilayangudi", "இளையான்குடி", "singampunari", "சிங்கம்புணரி", "kalaiyarkoil", "காளையார்கோவில்"]
    },

    # --------------------------------------------------------------------------
    # 35. RAMANATHAPURAM DISTRICT (இராமநாதபுரம்)
    # --------------------------------------------------------------------------
    {
        "name": "Rameswaram, Ramanathapuram District",
        "district": "Ramanathapuram",
        "latitude": "9.287600",
        "longitude": "79.312900",
        "keywords": ["rameswaram", "ராமேஸ்வரம்", "dhanushkodi", "தனுஷ்கோடி", "pamban bridge", "பாம்பன் பாலம்", "mandapam", "மண்டபம்"]
    },
    {
        "name": "Ramanathapuram Central, Ramanathapuram District",
        "district": "Ramanathapuram",
        "latitude": "9.363900",
        "longitude": "78.839500",
        "keywords": ["ramanathapuram", "ramnad", "இராமநாதபுரம்", "ராமநாதபுரம்", "paramakudi", "பரமக்குடி", "kilakarai", "கீழக்கரை", "mudukulathur", "முதுகுளத்தூர்", "kamuthi", "கமுதி", "tiruvadanai", "திருவாடானை"]
    },

    # --------------------------------------------------------------------------
    # 36. VIRUDHUNAGAR DISTRICT (விருதுநகர்)
    # --------------------------------------------------------------------------
    {
        "name": "Sivakasi, Virudhunagar District",
        "district": "Virudhunagar",
        "latitude": "9.453300",
        "longitude": "77.797200",
        "keywords": ["sivakasi", "சிவகாசி", "kutti japan", "குட்டி ஜப்பான்"]
    },
    {
        "name": "Rajapalayam & Srivilliputhur, Virudhunagar District",
        "district": "Virudhunagar",
        "latitude": "9.450000",
        "longitude": "77.550000",
        "keywords": ["rajapalayam", "ராஜபாளையம்", "srivilliputhur", "ஸ்ரீவில்லிபுத்தூர்", "andal temple", "ஆண்டாள் கோவில்", "watrap", "வத்திராயிருப்பு"]
    },
    {
        "name": "Virudhunagar Central, Virudhunagar District",
        "district": "Virudhunagar",
        "latitude": "9.587200",
        "longitude": "77.951400",
        "keywords": ["virudhunagar", "விருதுநகர்", "aruppukkottai", "அருப்புக்கோட்டை", "sattur", "சாத்தூர்", "kariapatti", "காரியாபட்டி"]
    },

    # --------------------------------------------------------------------------
    # 37. THENI DISTRICT (தேனி)
    # --------------------------------------------------------------------------
    {
        "name": "Bodinayakanur & Cumbum, Theni District",
        "district": "Theni",
        "latitude": "10.010000",
        "longitude": "77.350000",
        "keywords": ["bodi", "bodinayakanur", "போடிநாயக்கனூர்", "போடி", "cumbum", "கம்பம்", "chinnamanur", "சின்னமனூர்", "uthamapalayam", "உத்தமபாளையம்", "suruli falls", "சுருளி அருவி"]
    },
    {
        "name": "Theni Central, Theni District",
        "district": "Theni",
        "latitude": "10.010400",
        "longitude": "77.476800",
        "keywords": ["theni", "தேனி", "periyakulam", "பெரியகுளம்", "andipatti", "ஆண்டிபட்டி", "vaigai dam", "வைகை அணை"]
    },

    # --------------------------------------------------------------------------
    # 38. NILGIRIS DISTRICT (நீலகிரி)
    # --------------------------------------------------------------------------
    {
        "name": "Ooty (Udhagamandalam), Nilgiris District",
        "district": "Nilgiris",
        "latitude": "11.410200",
        "longitude": "76.695000",
        "keywords": ["ooty", "udhagamandalam", "ஊட்டி", "உதகமண்டலம்", "ooty lake", "botanical garden"]
    },
    {
        "name": "Coonoor & Kotagiri, Nilgiris District",
        "district": "Nilgiris",
        "latitude": "11.353000",
        "longitude": "76.795900",
        "keywords": ["coonoor", "குன்னூர்", "kotagiri", "கோத்தகிரி", "gudalur nilgiris", "கூடலூர்", "wellington", "வெலிங்டன்", "nilgiris", "நீலகிரி"]
    }
]


def extract_location(text: str) -> Tuple[Optional[str], Optional[str], Optional[str], float]:
    """
    Extracts specific Tamil Nadu location, taluk, town, and maps it strictly to its official District with GPS coordinates.
    Natively strips Tamil/Tanglish locative suffixes (-la, -il, -kitta, -pakkam, -ல, -இல்).
    Returns: (formatted_location_with_district, latitude, longitude, confidence)
    """
    if not text:
        return None, None, None, 0.0

    raw = text.strip()
    lowered = raw.lower()
    norm_text = unicodedata.normalize("NFC", lowered)

    # 1. High-precision Substring & Keyword Matching across all Tamil Nadu Districts
    best_loc = None
    highest_score = 0.0

    for loc in TAMIL_NADU_DISTRICT_LOCATIONS:
        for kw in loc["keywords"]:
            kw_norm = unicodedata.normalize("NFC", kw.lower())

            # Exact keyword occurrence
            if kw_norm in norm_text:
                score = 0.99 if kw_norm == norm_text else 0.95
                if score > highest_score:
                    highest_score = score
                    best_loc = loc

            # Tanglish suffix matching: e.g. "gandhipuram-la", "gandhipuramla", "coimbatore-la"
            tanglish_pattern = r'\b' + re.escape(kw_norm) + r'(?:[-_]?(?:la|le|il|yil|kitta|pakkam|road|street|nagar|bus stand))\b'
            if re.search(tanglish_pattern, norm_text):
                score = 0.96
                if score > highest_score:
                    highest_score = score
                    best_loc = loc

            # Tamil suffix matching: e.g. "காந்திபுரத்தில்", "காந்திபுரம்ல", "திருவாரூர்ல", "சென்னையில்", "மதுரையில"
            tamil_base = re.sub(r'(?:ல|இல்|யில்|இடம்|பக்கம்|அருகே|பஸ் ஸ்டாண்ட்)$', '', kw_norm)
            if len(tamil_base) >= 3 and tamil_base in norm_text:
                score = 0.94
                if score > highest_score:
                    highest_score = score
                    best_loc = loc

    if best_loc and highest_score >= 0.90:
        return best_loc["name"], best_loc["latitude"], best_loc["longitude"], highest_score

    # 2. Fuzzy Matching for spelling variations across all districts
    for loc in TAMIL_NADU_DISTRICT_LOCATIONS:
        for kw in loc["keywords"]:
            kw_norm = unicodedata.normalize("NFC", kw.lower())
            ratio = fuzz.token_set_ratio(kw_norm, norm_text)
            if ratio >= 80:
                calc_score = ratio / 100.0
                if calc_score > highest_score:
                    highest_score = calc_score
                    best_loc = loc

    if best_loc and highest_score >= 0.80:
        return best_loc["name"], best_loc["latitude"], best_loc["longitude"], round(highest_score, 2)

    # 3. Dynamic Grammatical Fallback extraction for unspecified localities
    location_patterns = [
        r'(?:near|at|opposite|in|around)\s+([A-Za-z0-9\s]{3,25})(?:\s+street|\s+road|\s+area|\s+nagar|\s+colony|\s+bus stand|\b)',
        r'([A-Za-z0-9]{3,20})\s*-\s*la\b',
        r'([A-Za-z0-9]{3,20})\s+pakkam\b',
        r'([A-Za-z0-9]{3,20})\s+kitta\b',
        r'([\u0B80-\u0BFF]{3,20})(?:ல|யில்|இல்|அருகே)\b'
    ]

    for pattern in location_patterns:
        match = re.search(pattern, norm_text)
        if match:
            candidate = match.group(1).strip()
            # Ignore common non-location filler words
            excluded = ["romba", "periya", "chinna", "the", "that", "this", "anga", "inga", "unga", "enaku", "namakku", "romba dark", "damage", "thanni", "current", "problem", "issue"]
            if candidate and len(candidate) > 2 and candidate.lower() not in excluded:
                formatted_loc = candidate.title() if candidate.isascii() else candidate
                return f"{formatted_loc}, Tamil Nadu", None, None, 0.70

    return None, None, None, 0.0
