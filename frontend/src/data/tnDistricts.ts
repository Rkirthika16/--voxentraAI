export interface TNDistrict {
  id: string;
  name: string;
  name_ta: string;
  headquarters: string;
  center: [number, number];
  zoom: number;
  region: 'Kongu / West' | 'North / Chennai' | 'South / Pandiya' | 'Central / Delta';
}

export const TN_STATE_CENTER: [number, number] = [11.1271, 78.6569];
export const TN_STATE_ZOOM = 7;

export const TN_38_DISTRICTS: TNDistrict[] = [
  // Kongu / Western Tamil Nadu
  { id: 'coimbatore', name: 'Coimbatore', name_ta: 'கோயம்புத்தூர்', headquarters: 'Coimbatore', center: [11.0168, 76.9558], zoom: 12, region: 'Kongu / West' },
  { id: 'tiruppur', name: 'Tiruppur', name_ta: 'திருப்பூர்', headquarters: 'Tiruppur', center: [11.1085, 77.3411], zoom: 12, region: 'Kongu / West' },
  { id: 'erode', name: 'Erode', name_ta: 'ஈரோடு', headquarters: 'Erode', center: [11.3410, 77.7172], zoom: 12, region: 'Kongu / West' },
  { id: 'salem', name: 'Salem', name_ta: 'சேலம்', headquarters: 'Salem', center: [11.6643, 78.1460], zoom: 12, region: 'Kongu / West' },
  { id: 'namakkal', name: 'Namakkal', name_ta: 'நாமக்கல்', headquarters: 'Namakkal', center: [11.2189, 78.1674], zoom: 12, region: 'Kongu / West' },
  { id: 'karur', name: 'Karur', name_ta: 'கரூர்', headquarters: 'Karur', center: [10.9601, 78.0766], zoom: 12, region: 'Kongu / West' },
  { id: 'dharmapuri', name: 'Dharmapuri', name_ta: 'தருமபுரி', headquarters: 'Dharmapuri', center: [12.1211, 78.1582], zoom: 12, region: 'Kongu / West' },
  { id: 'krishnagiri', name: 'Krishnagiri', name_ta: 'கிருஷ்ணகிரி', headquarters: 'Krishnagiri', center: [12.5186, 78.2138], zoom: 12, region: 'Kongu / West' },
  { id: 'nilgiris', name: 'Nilgiris', name_ta: 'நீலகிரி', headquarters: 'Udhagamandalam (Ooty)', center: [11.4102, 76.6950], zoom: 12, region: 'Kongu / West' },
  { id: 'dindigul', name: 'Dindigul', name_ta: 'திண்டுக்கல்', headquarters: 'Dindigul', center: [10.3673, 77.9803], zoom: 12, region: 'Kongu / West' },

  // Southern Tamil Nadu / Pandiya Nadu
  { id: 'tirunelveli', name: 'Tirunelveli', name_ta: 'திருநெல்வேலி', headquarters: 'Tirunelveli', center: [8.7139, 77.7567], zoom: 12, region: 'South / Pandiya' },
  { id: 'tenkasi', name: 'Tenkasi', name_ta: 'தென்காசி', headquarters: 'Tenkasi', center: [8.9594, 77.3142], zoom: 12, region: 'South / Pandiya' },
  { id: 'thoothukudi', name: 'Thoothukudi', name_ta: 'தூத்துக்குடி', headquarters: 'Thoothukudi', center: [8.7642, 78.1348], zoom: 12, region: 'South / Pandiya' },
  { id: 'kanyakumari', name: 'Kanyakumari', name_ta: 'கன்னியாகுமரி', headquarters: 'Nagercoil', center: [8.0883, 77.5385], zoom: 12, region: 'South / Pandiya' },
  { id: 'madurai', name: 'Madurai', name_ta: 'மதுரை', headquarters: 'Madurai', center: [9.9252, 78.1198], zoom: 12, region: 'South / Pandiya' },
  { id: 'theni', name: 'Theni', name_ta: 'தேனி', headquarters: 'Theni', center: [10.0104, 77.4768], zoom: 12, region: 'South / Pandiya' },
  { id: 'virudhunagar', name: 'Virudhunagar', name_ta: 'விருதுநகர்', headquarters: 'Virudhunagar', center: [9.5872, 77.9514], zoom: 12, region: 'South / Pandiya' },
  { id: 'ramanathapuram', name: 'Ramanathapuram', name_ta: 'இராமநாதபுரம்', headquarters: 'Ramanathapuram', center: [9.3639, 78.8395], zoom: 12, region: 'South / Pandiya' },
  { id: 'sivaganga', name: 'Sivaganga', name_ta: 'சிவகங்கை', headquarters: 'Sivaganga', center: [9.8433, 78.4800], zoom: 12, region: 'South / Pandiya' },

  // Northern Tamil Nadu / Chennai Metropolitan
  { id: 'chennai', name: 'Chennai', name_ta: 'சென்னை', headquarters: 'Chennai', center: [13.0827, 80.2707], zoom: 12, region: 'North / Chennai' },
  { id: 'chengalpattu', name: 'Chengalpattu', name_ta: 'செங்கல்பட்டு', headquarters: 'Chengalpattu', center: [12.6819, 79.9888], zoom: 12, region: 'North / Chennai' },
  { id: 'tiruvallur', name: 'Tiruvallur', name_ta: 'திருவள்ளூர்', headquarters: 'Tiruvallur', center: [13.1432, 79.9079], zoom: 12, region: 'North / Chennai' },
  { id: 'kanchipuram', name: 'Kanchipuram', name_ta: 'காஞ்சிபுரம்', headquarters: 'Kanchipuram', center: [12.8342, 79.7036], zoom: 12, region: 'North / Chennai' },
  { id: 'vellore', name: 'Vellore', name_ta: 'வேலூர்', headquarters: 'Vellore', center: [12.9165, 79.1325], zoom: 12, region: 'North / Chennai' },
  { id: 'ranipet', name: 'Ranipet', name_ta: 'ராணிப்பேட்டை', headquarters: 'Ranipet', center: [12.9272, 79.3325], zoom: 12, region: 'North / Chennai' },
  { id: 'tirupathur', name: 'Tirupathur', name_ta: 'திருப்பத்தூர்', headquarters: 'Tirupathur', center: [12.4950, 78.5678], zoom: 12, region: 'North / Chennai' },
  { id: 'tiruvannamalai', name: 'Tiruvannamalai', name_ta: 'திருவண்ணாமலை', headquarters: 'Tiruvannamalai', center: [12.2253, 79.0747], zoom: 12, region: 'North / Chennai' },
  { id: 'viluppuram', name: 'Viluppuram', name_ta: 'விழுப்புரம்', headquarters: 'Viluppuram', center: [11.9401, 79.4861], zoom: 12, region: 'North / Chennai' },
  { id: 'kallakurichi', name: 'Kallakurichi', name_ta: 'கள்ளக்குறிச்சி', headquarters: 'Kallakurichi', center: [11.7383, 78.9639], zoom: 12, region: 'North / Chennai' },
  { id: 'cuddalore', name: 'Cuddalore', name_ta: 'கடலூர்', headquarters: 'Cuddalore', center: [11.7480, 79.7714], zoom: 12, region: 'North / Chennai' },

  // Central / Cauvery Delta Tamil Nadu
  { id: 'tiruchirappalli', name: 'Tiruchirappalli', name_ta: 'திருச்சிராப்பள்ளி', headquarters: 'Tiruchirappalli (Trichy)', center: [10.7905, 78.7047], zoom: 12, region: 'Central / Delta' },
  { id: 'thanjavur', name: 'Thanjavur', name_ta: 'தஞ்சாவூர்', headquarters: 'Thanjavur', center: [10.7870, 79.1378], zoom: 12, region: 'Central / Delta' },
  { id: 'tiruvarur', name: 'Tiruvarur', name_ta: 'திருவாரூர்', headquarters: 'Tiruvarur', center: [10.7725, 79.6365], zoom: 12, region: 'Central / Delta' },
  { id: 'nagapattinam', name: 'Nagapattinam', name_ta: 'நாகப்பட்டினம்', headquarters: 'Nagapattinam', center: [10.7656, 79.8424], zoom: 12, region: 'Central / Delta' },
  { id: 'mayiladuthurai', name: 'Mayiladuthurai', name_ta: 'மயிலாடுதுறை', headquarters: 'Mayiladuthurai', center: [11.1075, 79.6522], zoom: 12, region: 'Central / Delta' },
  { id: 'pudukkottai', name: 'Pudukkottai', name_ta: 'புதுக்கோட்டை', headquarters: 'Pudukkottai', center: [10.3833, 78.8001], zoom: 12, region: 'Central / Delta' },
  { id: 'ariyalur', name: 'Ariyalur', name_ta: 'அரியலூர்', headquarters: 'Ariyalur', center: [11.1401, 79.0786], zoom: 12, region: 'Central / Delta' },
  { id: 'perambalur', name: 'Perambalur', name_ta: 'பெரம்பலூர்', headquarters: 'Perambalur', center: [11.2342, 78.8820], zoom: 12, region: 'Central / Delta' }
];

export const OSM_TILE_PROVIDERS = [
  {
    id: 'osm-standard',
    name: 'OpenStreetMap Standard',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
  },
  {
    id: 'carto-voyager',
    name: 'Carto Voyager (Clean Street Map)',
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://openstreetmap.org">OSM</a> | CartoDB',
    maxZoom: 19
  },
  {
    id: 'carto-dark',
    name: 'Carto Dark Matter (Night Mode)',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://openstreetmap.org">OSM</a> | CartoDB',
    maxZoom: 19
  },
  {
    id: 'esri-imagery',
    name: 'Satellite Aerial Imagery',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri & Earthstar Geographics',
    maxZoom: 18
  }
];
