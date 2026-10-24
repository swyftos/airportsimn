/**
 * sim-engine.js
 * Deterministic flight schedule & ramp parking simulator for LAX FBO Super Bowl LXI.
 * Strictly uses data from parking_data.json. No fake bookings; generated aircraft
 * are a seeded reproducible illustration matching the model's exact daily totals,
 * size mix, stay mix, and hourly distributions.
 *
 * Rule: Overflow aircraft wait for a manager decision and are NEVER refused.
 */

// PRNG: Mulberry32 for reproducible, seeded generation
function mulberry32(seed) {
  return function() {
    let t = (seed += 0x6D2B79F5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// String hash to 32-bit unsigned integer
function hashString(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 16777619);
  }
  return h >>> 0;
}

export class SimulationEngine {
  constructor(parkingData) {
    this.data = parkingData;
    this.situationKey = 'standard';
    this.scenarioKey = 'Medium'; // Default forecast scenario
    this.planState = {
      towPacking: true,
      overflowApron: true
    };

    // Week boundaries: Thu Feb 11 00:00 to Wed Feb 17 23:59:59 (7 days = 604,800 s)
    this.startDate = '2027-02-11';
    this.totalSeconds = 7 * 86400;

    // Generated flights roster
    this.flights = [];
    this.scheduleGenerated = false;

    // Build schedule
    this.generateSchedule();
  }

  setSituation(situationKey) {
    if (this.data.situations[situationKey]) {
      this.situationKey = situationKey;
      this.generateSchedule();
    }
  }

  setScenario(scenarioKey) {
    if (this.data.scenarios[scenarioKey]) {
      this.scenarioKey = scenarioKey;
      this.generateSchedule();
    }
  }

  setPlanState(towPackingApproved, overflowApronApproved) {
    this.planState.towPacking = !!towPackingApproved;
    this.planState.overflowApron = !!overflowApronApproved;
  }

  // Get current plan specification for current situation & scenario
  getCurrentPlan() {
    const sit = this.data.parking[this.situationKey];
    return sit?.plans?.[this.scenarioKey] || null;
  }

  // Get current day's model record
  getDayData(dateStr) {
    const sit = this.data.parking[this.situationKey];
    return sit?.days?.[this.scenarioKey]?.[dateStr] || null;
  }

  // Generate deterministic flight roster
  generateSchedule() {
    const seed = hashString(`${this.situationKey}_${this.scenarioKey}_sb61_lax`);
    const rng = mulberry32(seed);

    const sizes = this.data.aircraft.sizes;
    // Light: 0.47, Midsize: 0.33, Large: 0.20
    const lightShare = sizes.light.share;
    const midShare = sizes.midsize.share;

    const stays = this.data.aircraft.stays; // same_day 0.40, overnight 0.45, multi_day 0.15

    const hourShares = this.data.hourly_profile.shares;

    const daysList = this.data.days; // 7 days
    const flows = this.data.flows[this.scenarioKey];

    const flights = [];
    let idCounter = 1;

    // 1. Opening aircraft (at t = 0), count from data.aircraft.opening_aircraft, sizes from data.aircraft.sizes
    const openingTypes = ['light', 'light', 'midsize', 'light', 'midsize', 'large'];
    const openingDepHours = [6.5, 9.0, 11.2, 14.0, 17.5, 26.0];
    const openingConfigs = Array.from({ length: Math.round(this.data.aircraft.opening_aircraft) }, (_, i) => {
      const type = openingTypes[i % openingTypes.length];
      return { type, su: sizes[type].su, name: sizes[type].example.split(' (')[0], depHour: openingDepHours[i % openingDepHours.length] };
    });

    openingConfigs.forEach((cfg, idx) => {
      flights.push({
        id: `FL-OPEN-${idx + 1}`,
        tail: `N${100 + idx * 12}OP`,
        isOpening: true,
        type: cfg.type,
        modelName: cfg.name,
        su: cfg.su,
        arrivalTime: 0,
        departureTime: Math.round(cfg.depHour * 3600),
        stayType: 'transient_opening',
        dwellHours: cfg.depHour,
        colorIndex: idx % 5
      });
    });

    // Tail number prefixes based on type
    const tailPrefixes = { light: 'CJ', midsize: 'CL', large: 'GS' };

    // 2. Generate arrivals for each of the 7 days based on daily expected arrivals
    daysList.forEach((dayObj, dayIdx) => {
      const dateStr = dayObj.date;
      const dayFlow = flows[dateStr];
      const expectedArr = dayFlow ? dayFlow.expected_arrivals : 5.0;

      // Determine integer arrival count matching the decimal expectation
      // Floor + probability of fractional part
      const countFloor = Math.floor(expectedArr);
      const frac = expectedArr - countFloor;
      const arrivalsCount = countFloor + (rng() < frac ? 1 : 0);

      // Hourly profile distribution for this day
      const isWeekend = dayObj.day_type === 'weekend';
      const arrProfile = isWeekend ? hourShares.weekend_arrivals : hourShares.weekday_arrivals;

      // Build cumulative distribution
      const cdf = new Array(24);
      let sum = 0;
      for (let h = 0; h < 24; h++) {
        sum += arrProfile[h];
        cdf[h] = sum;
      }
      // Normalize
      for (let h = 0; h < 24; h++) {
        cdf[h] /= sum;
      }

      for (let i = 0; i < arrivalsCount; i++) {
        // Pick arrival hour from CDF
        const rHour = rng();
        let hour = 0;
        while (hour < 23 && rHour > cdf[hour]) {
          hour++;
        }
        // Random minute within hour
        const minute = rng() * 60;
        let arrSec = (dayIdx * 86400) + (hour * 3600) + Math.round(minute * 60);

        // Game-day security pause from parking_data.json (date, start, end): blocked arrivals land before it
        const gr = this.data.game_day_restriction;
        if (this.situationKey === 'security_restriction' && gr && dateStr === gr.date) {
          const toSec = t => { const [h, m] = t.split(':').map(Number); return dayIdx * 86400 + h * 3600 + m * 60; };
          const secStart = toSec(gr.start), secEnd = toSec(gr.end);
          if (arrSec >= secStart && arrSec <= secEnd) {
            arrSec = Math.max(dayIdx * 86400, secStart - Math.round(rng() * 3 * 3600));
          }
        }

        // Draw aircraft size from mix: Light 47%, Midsize 33%, Large 20%
        const rSize = rng();
        let aType = 'light';
        let aSu = sizes.light.su;
        let aName = sizes.light.example.split(' (')[0];

        if (rSize > lightShare + midShare) {
          aType = 'large';
          aSu = sizes.large.su;
          aName = sizes.large.example.split(' (')[0];
        } else if (rSize > lightShare) {
          aType = 'midsize';
          aSu = sizes.midsize.su;
          aName = sizes.midsize.example.split(' (')[0];
        }

        // Draw stay duration from stay mix: same_day (40%), overnight (45%), multi_day (15%)
        const rStay = rng();
        let stayType = 'same_day';
        let dwellHours = 2.5 + rng() * 4.5; // 2.5 to 7 hours

        if (rStay > stays.same_day + stays.overnight) {
          stayType = 'multi_day';
          dwellHours = 48 + rng() * 24; // 48 to 72 hours
        } else if (rStay > stays.same_day) {
          stayType = 'overnight';
          dwellHours = 18 + rng() * 8; // 18 to 26 hours
        }

        // Situation check: 24h departure delay after the game (Sun 14 Feb night onwards)
        if (this.situationKey === 'departure_delay_24h') {
          const gameIdx = daysList.findIndex(d => d.date === this.data.meta.game_day);
          const gameNight = gameIdx * 86400 + 18 * 3600; // game day 18:00
          const delayWindowEnd = (gameIdx + 2) * 86400;  // two days later, 00:00
          const initialDep = arrSec + Math.round(dwellHours * 3600);
          if (initialDep >= gameNight && initialDep <= delayWindowEnd) {
            dwellHours += 24.0; // Add 24h delay
          }
        }

        // Situation check: heavy rain on game day
        if (this.situationKey === 'heavy_rain' && dateStr === this.data.meta.game_day) {
          // Additional dwell due to weather holding
          if (hour >= 12 && hour <= 21) {
            dwellHours += 3.5;
          }
        }

        let depSec = arrSec + Math.round(dwellHours * 3600);
        // Cap departure time to slightly after end of week so we don't drop abruptly
        if (depSec > this.totalSeconds + 86400) {
          depSec = this.totalSeconds + 86400;
        }

        const tailNum = `N${200 + idCounter}${tailPrefixes[aType]}`;

        flights.push({
          id: `FL-${idCounter}`,
          tail: tailNum,
          isOpening: false,
          type: aType,
          modelName: aName,
          su: aSu,
          arrivalTime: arrSec,
          departureTime: depSec,
          stayType: stayType,
          dwellHours: Math.round(dwellHours * 10) / 10,
          colorIndex: idCounter % 6
        });

        idCounter++;
      }
    });

    // 3. Carry-over aircraft: the generated flights alone do not hold the model's daily stock, so each day is topped up
    // until its busiest moment matches the model's P50 parking demand. They stand for aircraft already on the ramp
    // (multi-day stays the flows do not show), not extra forecast arrivals. One ordered pool keeps the same
    // airframes parked from one day to the next.
    const carryRng = mulberry32(hashString(`${this.situationKey}_${this.scenarioKey}_carry`));
    const pool = [];
    const drawSize = () => {
      const r = carryRng();
      const type = r > lightShare + midShare ? 'large' : r > lightShare ? 'midsize' : 'light';
      return { type, su: sizes[type].su, modelName: sizes[type].example.split(' (')[0] };
    };
    const carryCount = daysList.map((dayObj, dayIdx) => {
      const target = this.getDayData(dayObj.date)?.parking_demand_su_p50 || 0;
      let rawPeak = 0;
      for (let t = dayIdx * 86400; t < (dayIdx + 1) * 86400; t += 900) {
        let su = 0;
        for (const f of flights) if (f.arrivalTime <= t && f.departureTime >= t) su += f.su;
        rawPeak = Math.max(rawPeak, su);
      }
      let n = 0, added = 0;
      while (rawPeak + added < target - sizes.light.su / 2) {
        if (n === pool.length) pool.push(drawSize());
        added += pool[n++].su;
      }
      return n;
    });
    pool.forEach((size, j) => {
      let start = null;
      for (let d = 0; d <= daysList.length; d++) {
        const present = d < daysList.length && j < carryCount[d];
        if (present && start === null) start = d;
        if (!present && start !== null) {
          flights.push({
            id: `FL-CARRY-${j + 1}-${start}`, tail: `N${700 + j}CO`, isOpening: true, isCarry: true,
            type: size.type, modelName: size.modelName, su: size.su,
            arrivalTime: start * 86400, departureTime: d * 86400 - 1,
            stayType: 'carry_over', dwellHours: (d - start) * 24, colorIndex: j % 6
          });
          start = null;
        }
      }
    });

    // Sort all flights by arrival time
    flights.sort((a, b) => a.arrivalTime - b.arrivalTime);
    this.flights = flights;
    this.scheduleGenerated = true;
  }

  /**
   * Query the simulation state at a specific second in the week [0 .. 604800].
   * Evaluates stand assignments, capacity rules, and manager overflow staging.
   */
  getStateAtTime(simSeconds) {
    const clampedSec = Math.max(0, Math.min(this.totalSeconds, simSeconds));

    // Calculate calendar date and time
    const dayIndex = Math.min(6, Math.floor(clampedSec / 86400));
    const secInDay = clampedSec % 86400;
    const hour = secInDay / 3600;
    const hourInt = Math.floor(hour);
    const minInt = Math.floor((secInDay % 3600) / 60);

    const currentDateObj = this.data.days[dayIndex];
    const dateStr = currentDateObj.date;

    const timeStr = `${String(hourInt).padStart(2, '0')}:${String(minInt).padStart(2, '0')}`;

    // Ramp capacities
    const normalRampCap = this.data.capacity.ramp_su; // 15.0 su
    // If tow packing is approved: +10% gain = 16.5 su
    const packedRampCap = normalRampCap * (1 + this.data.capacity.tow_packing_gain);
    const activeRampCap = this.planState.towPacking ? packedRampCap : normalRampCap;

    // Overflow leased apron:
    // Check if overflow lease is in the plan for this situation and scenario
    const plan = this.getCurrentPlan();
    const overflowAction = plan?.actions?.find(a => a.id === 'overflow_apron');
    // Leased SU for this scenario (e.g. 5 su in Medium standard)
    let leasedOverflowSu = 0;
    if (overflowAction && this.planState.overflowApron) {
      // Parse su from action string e.g. "Lease 5 su of the remote overflow apron"
      const match = overflowAction.action.match(/Lease\s+(\d+)\s+su/i);
      leasedOverflowSu = match ? parseFloat(match[1]) : 5.0;
    }

    // Active flights at clampedSec:
    // An aircraft is active if arrived and not yet departed.
    const activeFlights = [];
    for (const f of this.flights) {
      if (f.arrivalTime <= clampedSec && f.departureTime >= clampedSec) {
        // Taxi state: arriving if within first 120s of arrival; departing if within last 120s of departure
        let phase = 'parked';
        if (clampedSec - f.arrivalTime < 120 && !f.isOpening) {
          phase = 'taxi_in';
        } else if (f.departureTime - clampedSec < 120) {
          phase = 'taxi_out';
        }
        activeFlights.push({ ...f, phase });
      }
    }

    // Allocate parking spots deterministically based on arrival order
    // Order by arrivalTime
    activeFlights.sort((a, b) => a.arrivalTime - b.arrivalTime);

    let mainRampUsedSu = 0;
    let overflowUsedSu = 0;
    let decisionAreaSu = 0;

    const allocatedAircraft = [];

    // Stand slots on Main Ramp (10 marked spots totaling 15 su):
    // 4 Light (1.0 su each), 4 Midsize (1.5 su each), 2 Large (2.5 su each) = 15 su
    // In packed mode, stands allow tighter packing up to 16.5 su.
    const mainStands = [
      { id: 'S1', type: 'light', su: 1.0, occupied: false },
      { id: 'S2', type: 'light', su: 1.0, occupied: false },
      { id: 'S3', type: 'light', su: 1.0, occupied: false },
      { id: 'S4', type: 'light', su: 1.0, occupied: false },
      { id: 'S5', type: 'midsize', su: 1.5, occupied: false },
      { id: 'S6', type: 'midsize', su: 1.5, occupied: false },
      { id: 'S7', type: 'midsize', su: 1.5, occupied: false },
      { id: 'S8', type: 'midsize', su: 1.5, occupied: false },
      { id: 'S9', type: 'large', su: 2.5, occupied: false },
      { id: 'S10', type: 'large', su: 2.5, occupied: false },
      // Supplementary packed stand if tow packing enabled
      { id: 'S-PACK1', type: 'midsize', su: 1.5, occupied: false, isPacked: true }
    ];

    // Overflow apron stands (up to 8 stands)
    const overflowStands = [
      { id: 'O1', type: 'large', su: 2.5, occupied: false },
      { id: 'O2', type: 'large', su: 2.5, occupied: false },
      { id: 'O3', type: 'midsize', su: 1.5, occupied: false },
      { id: 'O4', type: 'midsize', su: 1.5, occupied: false },
      { id: 'O5', type: 'light', su: 1.0, occupied: false },
      { id: 'O6', type: 'light', su: 1.0, occupied: false }
    ];

    // Manager decision staging slots (overflow waiting area)
    const decisionSlots = [
      { id: 'DEC-1', occupied: false },
      { id: 'DEC-2', occupied: false },
      { id: 'DEC-3', occupied: false },
      { id: 'DEC-4', occupied: false },
      { id: 'DEC-5', occupied: false },
      { id: 'DEC-6', occupied: false },
      { id: 'DEC-7', occupied: false },
      { id: 'DEC-8', occupied: false }
    ];

    for (const plane of activeFlights) {
      const planeSu = plane.su;
      let assignedLocation = null;
      let assignedStand = null;

      // Rule 1: Try Main Ramp if capacity allows
      if (mainRampUsedSu + planeSu <= activeRampCap + 0.05) {
        // Find best matching stand on main ramp
        const stand = mainStands.find(s => !s.occupied && (!s.isPacked || this.planState.towPacking));
        if (stand) {
          stand.occupied = true;
          assignedStand = stand.id;
          assignedLocation = 'main_ramp';
          mainRampUsedSu += planeSu;
        }
      }

      // Rule 2: If Main Ramp full, check Overflow Apron (if plan approved and leased)
      if (!assignedLocation && leasedOverflowSu > 0) {
        if (overflowUsedSu + planeSu <= leasedOverflowSu + 0.05) {
          const oStand = overflowStands.find(s => !s.occupied);
          if (oStand) {
            oStand.occupied = true;
            assignedStand = oStand.id;
            assignedLocation = 'overflow_apron';
            overflowUsedSu += planeSu;
          }
        }
      }

      // Rule 3: If neither has capacity, aircraft waits in "Awaiting Manager Decision Area"
      // HARD RULE: Overflow aircraft wait for a manager decision and are NEVER refused.
      if (!assignedLocation) {
        const dSlot = decisionSlots.find(s => !s.occupied);
        assignedStand = dSlot ? dSlot.id : `DEC-${decisionSlots.length + 1}`;
        if (dSlot) dSlot.occupied = true;
        assignedLocation = 'manager_decision_area';
        decisionAreaSu += planeSu;
      }

      allocatedAircraft.push({
        ...plane,
        location: assignedLocation,
        standId: assignedStand
      });
    }

    // Get model benchmark data for this day from parking_data.json
    const modelDay = this.getDayData(dateStr);

    return {
      simSeconds: clampedSec,
      dayIndex,
      dateStr,
      weekday: currentDateObj.weekday,
      isGameDay: currentDateObj.game_day,
      isPresidentsDay: currentDateObj.presidents_day,
      timeStr,
      hourFloat: hour,
      // Operational aircraft counts
      activeAircraft: allocatedAircraft,
      activeCount: allocatedAircraft.length,
      // Ramp metrics
      mainRampUsedSu: Math.round(mainRampUsedSu * 10) / 10,
      mainRampCap: activeRampCap,
      mainRampNormalCap: normalRampCap,
      overflowUsedSu: Math.round(overflowUsedSu * 10) / 10,
      overflowLeasedCap: leasedOverflowSu,
      managerDecisionSu: Math.round(decisionAreaSu * 10) / 10,
      managerDecisionCount: allocatedAircraft.filter(a => a.location === 'manager_decision_area').length,
      // Model benchmark for the current day
      modelDay: modelDay || null,
      planState: { ...this.planState },
      situationKey: this.situationKey,
      scenarioKey: this.scenarioKey
    };
  }

  // Get week forecast list for charts & timeline strip
  getWeekSummary() {
    const sit = this.data.parking[this.situationKey];
    const scenarioDays = sit?.days?.[this.scenarioKey] || {};
    const ordinaryDays = this.data.ordinary_week || {};

    return this.data.days.map((d, idx) => {
      const dateStr = d.date;
      const model = scenarioDays[dateStr] || {};
      const ord = ordinaryDays[dateStr] || {};

      return {
        index: idx,
        date: dateStr,
        weekday: d.weekday,
        isGameDay: d.game_day,
        isPresidentsDay: d.presidents_day,
        p10: model.parking_demand_su_p10 || 0,
        p50: model.parking_demand_su_p50 || 0,
        p90: model.parking_demand_su_p90 || 0,
        capacityNormal: model.capacity_normal_su || 15.0,
        capacityPrepared: model.capacity_prepared_su || 21.5,
        probOverNormal: model.prob_over_normal_capacity || 0,
        probOverPrepared: model.prob_over_prepared_capacity || 0,
        riskLevel: model.risk_level || 'Low',
        arrivalsP50: model.arrivals_p50 || 0,
        departuresP50: model.departures_p50 || 0,
        utilizationNormalP50: model.utilization_normal_p50 || 0,
        // Ordinary week baseline
        ordP50: ord.parking_demand_su_p50 || 0,
        ordProbOver: ord.prob_over_normal_capacity || 0
      };
    });
  }
}
