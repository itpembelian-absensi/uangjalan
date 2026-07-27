export const ROUTE_FEE_VEHICLE_ORDER = ['grandmax', 'tronton', 'fuso', 'double', 'engkle', 'engkel', 'viar'];

export const ROUTE_FEE_CATEGORY_LABELS = {
  grandmax: 'Grand Max',
  engkle: 'Engkle',
  double: 'Double',
  fuso: 'Fuso',
  tronton: 'Tronton',
  viar: 'Viar',
};

export const ROUTE_FEE_DEFS = [
  {
    key: 'pjr',
    label: 'PJR',
    apiPath: 'pjr',
    path: '/master-pjr',
    title: 'Master PJR',
    defaults: { grandmax: 30000, engkle: 30000, double: 30000, fuso: 60000, tronton: 60000 },
  },
  {
    key: 'forklift_bongkaran',
    label: 'Forklift Bongkaran',
    apiPath: 'forklift_bongkaran',
    path: '/master-forklift-bongkaran',
    title: 'Master Forklift Bongkaran',
    defaults: { grandmax: 10000, engkle: 10000, double: 30000, fuso: 30000, tronton: 30000 },
  },
  {
    key: 'parkir_liar',
    label: 'Parkir Liar',
    apiPath: 'parkir_liar',
    path: '/master-parkir-liar',
    title: 'Master Parkir Liar',
    defaults: { grandmax: 5000, engkle: 5000, double: 5000, fuso: 10000, tronton: 10000 },
  },
  {
    key: 'parkir_kawasan',
    label: 'Parkir Kawasan',
    apiPath: 'parkir_kawasan',
    path: '/master-parkir-kawasan',
    title: 'Master Parkir Kawasan',
    defaults: { grandmax: 10000, engkle: 10000, double: 10000, fuso: 20000, tronton: 20000, viar: 10000 },
  },
];

export const PELABUHAN_VEHICLE_ORDER = ['grandmax', 'tronton', 'fuso', 'double', 'engkle', 'engkel'];

export const PELABUHAN_MASTER_LABELS = {
  grandmax: 'Grand Max',
  engkle: 'Engkle',
  double: 'Double',
  fuso: 'Fuso',
  tronton: 'Tronton',
};

export const PELABUHAN_DEFAULTS = {
  grandmax: 30000,
  engkle: 30000,
  double: 30000,
  fuso: 33000,
  tronton: 33000,
};

export const matchRouteFeeCategory = (name) => {
  const normalized = String(name || '').toLowerCase().replace(/[\s-]/g, '');
  for (const key of ROUTE_FEE_VEHICLE_ORDER) {
    if (normalized.includes(key)) return key === 'engkel' ? 'engkle' : key;
  }
  return null;
};

export const matchPelabuhanCategory = (name) => {
  const normalized = String(name || '').toLowerCase().replace(/[\s-]/g, '');
  for (const key of PELABUHAN_VEHICLE_ORDER) {
    if (normalized.includes(key)) return key === 'engkel' ? 'engkle' : key;
  }
  return null;
};

export const getUangPelabuhanAmount = (vehicleTypeId, vehicleTypes, pelabuhanMasters = []) => {
  const vt = (vehicleTypes || []).find((v) => String(v.id) === String(vehicleTypeId));
  const fromApi = Number(vt?.uang_pelabuhan_amount) || 0;
  if (fromApi > 0) return fromApi;

  const category = matchPelabuhanCategory(vt?.name);
  if (!category) return 0;

  const masterName = PELABUHAN_MASTER_LABELS[category];
  const master = (pelabuhanMasters || []).find((m) => m.name === masterName);
  if (master) return Number(master.amount) || 0;

  return PELABUHAN_DEFAULTS[category] || 0;
};

export const getRouteFeeAmount = (feeKey, vehicleTypeId, vehicleTypes, feeMasters = {}) => {
  const feeDef = ROUTE_FEE_DEFS.find((f) => f.key === feeKey);
  if (!feeDef) return 0;
  const vt = (vehicleTypes || []).find((v) => String(v.id) === String(vehicleTypeId));
  if (!vt) return 0;

  const category = matchRouteFeeCategory(vt.name);
  if (category) {
    const masterName = ROUTE_FEE_CATEGORY_LABELS[category];
    const master = (feeMasters[feeKey] || []).find((m) => m.name === masterName);
    if (master) return Number(master.amount) || 0;
    return feeDef.defaults[category] || 0;
  }

  // Fallback: cocokkan nama master dengan nama jenis kendaraan (mis. "Viar")
  const vtNorm = String(vt.name || '')
    .toLowerCase()
    .replace(/[\s-]/g, '');
  const master = (feeMasters[feeKey] || []).find((m) => {
    const mNorm = String(m.name || '')
      .toLowerCase()
      .replace(/[\s-]/g, '');
    return mNorm && (vtNorm === mNorm || vtNorm.includes(mNorm));
  });
  return master ? Number(master.amount) || 0 : 0;
};

/** Default checklist biaya rute: centang ON jika nominal master/default > 0 */
export const defaultIncludesForVehicle = (vehicleTypeId, vehicleTypes, feeMasters = {}) => {
  const includes = {};
  for (const fee of ROUTE_FEE_DEFS) {
    const amount = getRouteFeeAmount(fee.key, vehicleTypeId, vehicleTypes, feeMasters);
    includes[`include_${fee.key}`] = amount > 0;
  }
  return includes;
};

export const ROUTE_FEE_DISPLAY = [
  { key: 'uang_pelabuhan', label: 'Uang Pelabuhan', includeKey: 'include_uang_pelabuhan', amountKey: 'uang_pelabuhan' },
  ...ROUTE_FEE_DEFS.map((fee) => ({
    key: fee.key,
    label: fee.label,
    includeKey: `include_${fee.key}`,
    amountKey: fee.key,
  })),
];

export const sumRouteFees = (obj) => {
  let total = 0;
  if (obj?.include_uang_pelabuhan) total += Number(obj.uang_pelabuhan) || 0;
  for (const fee of ROUTE_FEE_DEFS) {
    if (obj?.[`include_${fee.key}`]) total += Number(obj[fee.key]) || 0;
  }
  return total;
};

export const getActiveRouteFeeLines = (obj) => {
  const lines = [];
  if (obj?.include_uang_pelabuhan && Number(obj.uang_pelabuhan) > 0) {
    lines.push({ label: 'Uang Pelabuhan', amount: Number(obj.uang_pelabuhan) || 0 });
  }
  for (const fee of ROUTE_FEE_DEFS) {
    if (!obj?.[`include_${fee.key}`]) continue;
    const amount = Number(obj[fee.key]) || 0;
    if (amount > 0) lines.push({ label: fee.label, amount });
  }
  return lines;
};

export const defaultRouteFeeFormFields = () => ({
  include_uang_pelabuhan: false,
  uang_pelabuhan: 0,
  include_pjr: true,
  pjr: 0,
  include_forklift_bongkaran: true,
  forklift_bongkaran: 0,
  include_parkir_liar: true,
  parkir_liar: 0,
  include_parkir_kawasan: true,
  parkir_kawasan: 0,
});

export const routeFeeAmountsFromApi = (obj) => {
  const result = {};
  for (const fee of ROUTE_FEE_DISPLAY) {
    result[fee.includeKey] = Boolean(obj?.[fee.includeKey]);
    result[fee.amountKey] = Number(obj?.[fee.amountKey]) || 0;
  }
  return result;
};

export const routeFeeFieldsFromApi = (route) => ({
  include_uang_pelabuhan: Boolean(route.include_uang_pelabuhan),
  include_pjr: Boolean(route.include_pjr),
  include_forklift_bongkaran: Boolean(route.include_forklift_bongkaran),
  include_parkir_liar: Boolean(route.include_parkir_liar),
  include_parkir_kawasan: Boolean(route.include_parkir_kawasan),
});

export const routeFeePayloadFromForm = (form) => ({
  include_uang_pelabuhan: Boolean(form.include_uang_pelabuhan),
  include_pjr: Boolean(form.include_pjr),
  include_forklift_bongkaran: Boolean(form.include_forklift_bongkaran),
  include_parkir_liar: Boolean(form.include_parkir_liar),
  include_parkir_kawasan: Boolean(form.include_parkir_kawasan),
});
