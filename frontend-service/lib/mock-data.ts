// Placeholder data until the supplier, order and credit services are wired up.
// Stores mirror data/csv/supplier-seed-data.csv at the repo root.

export type StoreType = 'Food' | 'Food/Coffee' | 'Shopping' | 'Printing';

export type Store = {
  id: string;
  name: string;
  type: StoreType;
  building: string;
  floor: number;
  locationDescription: string;
};

export type Favor = {
  id: string;
  requester: { name: string; rating: number; favors: number };
  pickup: string;
  deliverTo: string;
  items: string;
  credits: number;
  minutesAgo: number;
  distanceMeters: number;
};

export type ErrandRole = 'requester' | 'courier';

export type ErrandStatus =
  | 'open'
  | 'accepted'
  | 'picked_up'
  | 'completed'
  | 'cancelled'
  | 'expired';

export type Errand = {
  id: number;
  role: ErrandRole;
  status: ErrandStatus;
  title: string;
  store: string;
  date: string;
  credits: number;
};

export const CREDIT_BALANCE = 45;

export const stores: Store[] = [
  {
    id: 'annas-soup-union',
    name: "Anna's x Soup Union",
    type: 'Food',
    building: 'Central Library',
    floor: 1,
    locationDescription: 'Next to NUS Co-op',
  },
  {
    id: 'nus-coop',
    name: 'NUS Co-op',
    type: 'Shopping',
    building: 'Central Library',
    floor: 1,
    locationDescription: 'Inside the library on the right side',
  },
  {
    id: 'printer-com2',
    name: 'Printer @ Com 2',
    type: 'Printing',
    building: 'COM2',
    floor: 1,
    locationDescription: 'Next to LT19',
  },
  {
    id: 'robot-cafe',
    name: 'Cafe+ Robot Cafe',
    type: 'Food/Coffee',
    building: 'Central Library',
    floor: 1,
    locationDescription: 'Opp to central library entrance',
  },
  {
    id: 'a-hot-hideout',
    name: 'A Hot Hideout',
    type: 'Food',
    building: "Prince George's Park",
    floor: 2,
    locationDescription: 'Near PGP entrance',
  },
];

export const favors: Favor[] = [
  {
    id: 'f1',
    requester: { name: 'Wan Xin', rating: 4.9, favors: 48 },
    pickup: 'The Coffee Roaster @ AS8',
    deliverTo: 'PGP Foyer Block 12',
    items: 'Iced Latte + Blueberry Muffin (Less sweet)',
    credits: 8,
    minutesAgo: 12,
    distanceMeters: 350,
  },
  {
    id: 'f2',
    requester: { name: 'Maximus Lim', rating: 4.9, favors: 48 },
    pickup: 'NUS Co-op @ Central Library',
    deliverTo: 'Cinnamon College L4 Lounge',
    items: 'A4 Grid Notebook + Blue Pilot G2 Pen',
    credits: 12,
    minutesAgo: 45,
    distanceMeters: 800,
  },
  {
    id: 'f3',
    requester: { name: 'Lisa Drew', rating: 4.9, favors: 48 },
    pickup: 'Central Square @ YIH',
    deliverTo: 'Sheares Hall Admin Office',
    items: 'Chicken Chop Rice (Collect at Stall 4)',
    credits: 15,
    minutesAgo: 30,
    distanceMeters: 1200,
  },
  {
    id: 'f4',
    requester: { name: 'Arjun Nair', rating: 4.7, favors: 21 },
    pickup: 'Printer @ Com 2',
    deliverTo: 'COM1 Level 2 Study Area',
    items: 'Print CS3219 lecture notes (24 pgs B&W, stapled)',
    credits: 5,
    minutesAgo: 8,
    distanceMeters: 150,
  },
  {
    id: 'f5',
    requester: { name: 'Chloe Tan', rating: 5.0, favors: 63 },
    pickup: 'TOMORO COFFEE @ HSSML',
    deliverTo: 'BIZ2 Level 3 Seminar Room',
    items: 'Hot Americano x2 (no sugar)',
    credits: 10,
    minutesAgo: 25,
    distanceMeters: 500,
  },
  {
    id: 'f6',
    requester: { name: 'Daniel Ong', rating: 4.8, favors: 12 },
    pickup: 'Cheers @ E3',
    deliverTo: 'E4 Level 5 Lab',
    items: '2x Pocari Sweat + Tissue Pack',
    credits: 6,
    minutesAgo: 55,
    distanceMeters: 250,
  },
];

export const errands: Errand[] = [
  {
    id: 101,
    role: 'requester',
    status: 'picked_up',
    title: 'MacBook Charger (65W USB-C)',
    store: 'NUS Co-op @ Central Library',
    date: 'Today, 2:30 PM',
    credits: 15,
  },
  {
    id: 102,
    role: 'requester',
    status: 'completed',
    title: 'Print Handout (12 pgs B&W)',
    store: 'Goh Bros E-Print @ YIH',
    date: 'Yesterday',
    credits: 5,
  },
  {
    id: 103,
    role: 'courier',
    status: 'completed',
    title: 'Hot Americano + Egg Mayo Toast',
    store: 'The Coffee Roaster @ AS8',
    date: '14 Oct',
    credits: 10,
  },
  {
    id: 104,
    role: 'courier',
    status: 'cancelled',
    title: 'Calculus Textbook (MA1505)',
    store: 'NUS Co-op @ Central Library',
    date: '12 Oct',
    credits: 8,
  },
  {
    id: 105,
    role: 'requester',
    status: 'open',
    title: 'Iced Latte + Blueberry Muffin',
    store: 'The Coffee Roaster @ AS8',
    date: 'Today, 3:10 PM',
    credits: 8,
  },
  {
    id: 106,
    role: 'requester',
    status: 'expired',
    title: 'A4 Grid Notebook',
    store: 'NUS Co-op @ Central Library',
    date: '10 Oct',
    credits: 6,
  },
  {
    id: 107,
    role: 'courier',
    status: 'accepted',
    title: 'Print CS3219 lecture notes (24 pgs)',
    store: 'Printer @ Com 2',
    date: 'Today, 1:45 PM',
    credits: 5,
  },
];
