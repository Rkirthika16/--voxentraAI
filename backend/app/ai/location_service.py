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
    # --------------------------------------------------------------------------
    {
        "name": "Gandhipuram, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.014092",
        "longitude": "76.966940",
        "keywords": ["gandhipuram", "காந்திபுரம்", "gandhipuram bus stand", "gandhipuram central"]
    },
    {
        "name": "RS Puram, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.008321",
        "longitude": "76.949056",
        "keywords": ["rs puram", "r s puram", "rspuram", "ஆர் எஸ் புரம்", "ஆர்.எஸ்.புரம்", "டி பி ரோடு", "db road"]
    },
    {
        "name": "Peelamedu, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.026110",
        "longitude": "77.008240",
        "keywords": ["peelamedu", "பீளமேடு", "psg tech", "hopes college", "ஹோப்ஸ்"]
    },
    {
        "name": "Ukkadam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.988220",
        "longitude": "76.960240",
        "keywords": ["ukkadam", "உக்கடம்", "ukkadam bus stand", "உக்கடம் பஸ் ஸ்டாண்ட்"]
    },
    {
        "name": "Singanallur, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.998400",
        "longitude": "77.025600",
        "keywords": ["singanallur", "சிங்காநல்லூர்", "singanallur bus stand", "சிங்காநல்லூர் பஸ் நிலையம்"]
    },
    {
        "name": "Saravanampatti, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.077200",
        "longitude": "76.997500",
        "keywords": ["saravanampatti", "சரவணம்பட்டி", "saravanampatty", "it corridor coimbatore"]
    },
    {
        "name": "Mettupalayam, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.300000",
        "longitude": "76.950000",
        "keywords": ["mettupalayam", "மேட்டுப்பாளையம்", "karamadai", "காரமடை"]
    },
    {
        "name": "Pollachi, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "10.660000",
        "longitude": "77.010000",
        "keywords": ["pollachi", "பொள்ளாச்சி", "kinathukadavu", "கிணத்துக்கடவு", "valparai", "வால்பாறை", "ஆனைமலை", "anaimalai"]
    },
    {
        "name": "Coimbatore Central, Coimbatore District",
        "district": "Coimbatore",
        "latitude": "11.016800",
        "longitude": "76.955800",
        "keywords": ["coimbatore", "kovai", "கோயம்புத்தூர்", "கோவை", "ganapathy", "கணபதி", "thudiyalur", "துடியலூர்", "saibaba colony", "சாயிபாபா காலனி", "vadavalli", "வடவள்ளி", "perur", "பேரூர்", "sulur", "சூலூர்", "annur", "அன்னூர்"]
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
        "name": "Palayamkottai, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.718300",
        "longitude": "77.746100",
        "keywords": ["palayamkottai", "பாளை", "பாளையங்கோட்டை", "oxford of south india"]
    },
    {
        "name": "Ambasamudram, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.705000",
        "longitude": "77.458900",
        "keywords": ["ambasamudram", "அம்பாசமுத்திரம்", "cheranmahadevi", "சேரன்மகாதேவி", "manimuthar", "மணிமுத்தாறு", "papanasam nellai", "பாபநாசம் நெல்லை", "kalakkad", "களக்காடு"]
    },
    {
        "name": "Tirunelveli Central, Tirunelveli District",
        "district": "Tirunelveli",
        "latitude": "8.713900",
        "longitude": "77.756700",
        "keywords": ["tirunelveli", "nellai", "திருநெல்வேலி", "நெல்லை", "nanguneri", "நாங்குநேரி", "radhapuram", "ராதாபுரம்", "vallioor", "வள்ளியூர்"]
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
