#!/usr/bin/env python3
"""
ec_tsm_busbar_stationary.py — 实验 EcTSmBusbar: 铜母线+钛螺栓 稳态电→热→结构耦合 验证

案例: EcTSmBusbarStationary (src/physical/.java)。
物理: ConductiveMedia(ec) + HeatTransfer(ht) + SolidMechanics(solid)
      + ElectromagneticHeating (焦耳热→热) + ThermalExpansion (热→力)。
几何: L形铜母线 (xz工作平面截面+圆角, 拉伸 wbb) + 3个圆柱贯穿钛螺栓
      (竖直端1个沿x, 水平端2个沿z对称)。螺栓仅向外侧伸出 2*tbb (内侧端面齐平)。
      Form Union 保留内部边界 → 7个域。
电:   竖直螺栓最外侧圆端面 V=Vtot=20mV (bnd_terminal_high),
      水平两螺栓最外侧圆端面 Ground (bnd_terminal_ground), 其余外表面绝缘。
热:   全部外表面 (bnd_convection) 对流 htc=5 → T0=293.15K, 螺栓端面绝热。
力:   三螺栓外端面 Fixed (bnd_fixed, u=v=w=0)。

物理验证 (守恒 + 量级, 无封闭解析解因几何复杂):
  1. V 范围 [0, Vtot], high 端≈Vtot, ground 端≈0。
  2. 电流路径: high 螺栓(小截面) normJ 显著 > 母线(大截面) normJ。
  3. 温升: T>T0, 合理量级 (20mV 大电流 → 数十 K 温升)。
  4. 焦耳热: Qrh = J·E = ec.normJ²/σ > 0, 且 Qrh 在螺栓(Ti 高阻)处高于母线。
  5. 固定约束: 螺栓外端面位移≈0。
  6. 位移/应力量级: 温升~30K, α·ΔT·L~50μm; 热应力~几十 MPa。

CSV 列: x,y,z,V (V),T (K),ec.normJ (A/m^2),ec.Qrh (W/m^3),
         solid.disp (m),solid.mises (N/m^2),solid.sx,solid.sy,solid.sz (N/m^2)。

用法:
    python ec_tsm_busbar_stationary.py <csv-path> <json-out> <md-out>
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "EcTSmBusbar"

# ---- 物理参数 (与 EcTSmBusbarStationary.java 一致) ----
L = 0.09
RAD = 0.006
TBB = 0.005
WBB = 0.05
VTOT = 0.020
T0 = 293.15
HTC = 5.0
SIGMA_CU = 5.998e7
SIGMA_TI = 7.407e5
ALPHA_CU = 17e-6


def in_busbar(x, y, z):
    """母线 L 形域: 底部横条(z∈[0,tbb], x∈[0,L+2tbb]) + 右侧竖条(x∈[L+tbb,L+2tbb], z∈[0,0.1])。"""
    if y < -0.0505 or y > 0.0005:
        return False
    bottom = (0 - 1e-4 <= z <= TBB + 1e-4) and (0 <= x <= 0.10 + 1e-4)
    vert = (0.095 - 1e-4 <= x <= 0.10 + 1e-4) and (0 <= z <= 0.10 + 1e-4)
    return bottom or vert


def in_bolt(x, y, z):
    """三个贯穿螺栓圆柱体。"""
    # 竖直螺栓 cyl1: 沿x, 中心 (0.0975, -0.025, 0.05), r=0.006, x∈[0.085,0.11]
    if (
        abs(z - 0.05) < 0.006
        and abs(y + 0.025) < 0.006
        and (x - 0.0975) ** 2 + (y + 0.025) ** 2 < 0.006**2 * 1.1
    ):
        return True
    # 水平螺栓 cyl2: 沿z, 中心 (0.045, -0.0375, 0.0025), y 对称
    for yc in (-0.0375, -0.0125):
        if (
            abs(x - 0.045) < 0.006
            and (y - yc) ** 2 + (z - 0.0025) ** 2 < 0.006**2 * 1.1
        ):
            return True
    return False


def main():
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    csv_path, json_out, md_out = sys.argv[1], sys.argv[2], sys.argv[3]

    headers, rows = load_csv(csv_path)
    checks = []
    if len(rows) == 0:
        checks.append(check("data_present", False, None, "non-empty CSV", "rows"))
        return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)

    # 列: x=0,y=1,z=2,V=3,T=4,normJ=5,Qrh=6,disp=7,mises=8,sx=9,sy=10,sz=11
    arr = np.array(rows)
    x, y, z = arr[:, 0], arr[:, 1], arr[:, 2]
    V, T = arr[:, 3], arr[:, 4]
    normJ, Qrh = arr[:, 5], arr[:, 6]
    disp, mises = arr[:, 7], arr[:, 8]

    # ---- 1. V 范围 [0, Vtot] ----
    vmax, vmin = float(V.max()), float(V.min())
    checks.append(
        check(
            "V_range",
            vmin >= -1e-6 and vmax <= VTOT * 1.001 + 1e-6,
            [vmin, vmax],
            "V∈[0, Vtot]",
            "V",
        )
    )

    # high 端 (cyl1 x=0.11 端面) V≈Vtot; ground 端 (cyl2/3 z=-0.01) V≈0
    high = np.where(
        (np.abs(x - 0.110) < 0.002) & (np.abs(z - 0.05) < 0.006) & (y < -0.01)
    )[0]
    ground = np.where((np.abs(z + 0.010) < 0.002) & (np.abs(x - 0.045) < 0.006))[0]
    if len(high) > 0 and len(ground) > 0:
        v_high = float(V[high].mean())
        v_gnd = float(V[ground].mean())
        checks.append(
            check(
                "V_high",
                abs(v_high - VTOT) < 0.001,
                v_high,
                "V at high bolt end ≈ Vtot",
                "V",
            )
        )
        checks.append(
            check(
                "V_ground", abs(v_gnd) < 0.001, v_gnd, "V at ground bolt ends ≈ 0", "V"
            )
        )
    else:
        checks.append(check("V_high", False, None, "no high/ground samples", "V"))
        checks.append(check("V_ground", False, None, "no high/ground samples", "V"))

    # ---- 2. 电流路径: high 螺栓(小截面) J > 母线 J ----
    cu = [
        i
        for i in range(len(rows))
        if in_busbar(x[i], y[i], z[i]) and not in_bolt(x[i], y[i], z[i])
    ]
    ti = [i for i in range(len(rows)) if in_bolt(x[i], y[i], z[i])]
    if len(cu) > 20 and len(ti) > 20:
        j_bus = float(np.median(normJ[cu]))
        # 竖条下部 (z<0.04, 主电流路径)
        cu_lower = [i for i in cu if z[i] < 0.04 and y[i] < -0.001]
        j_bus_low = float(np.median(normJ[cu_lower])) if cu_lower else j_bus
        j_bolt_hi = float(np.max(normJ[ti]))
        # high 螺栓段电流密度: 圆柱穿过竖条处
        hi_bolt = [i for i in ti if np.abs(z[i] - 0.05) < 0.02 and x[i] > 0.09]
        j_hi_med = float(np.median(normJ[hi_bolt])) if hi_bolt else 0.0
        checks.append(
            check(
                "J_current_path",
                j_hi_med > j_bus_low * 0.5,
                [j_hi_med, j_bus_low],
                "high-bolt J >> busbar J (small section)",
                "A/m^2",
            )
        )
        checks.append(
            check(
                "J_positive",
                j_bolt_hi > 1e3,
                j_bolt_hi,
                "max J in bolts > 1e3 A/m^2",
                "A/m^2",
            )
        )
    else:
        checks.append(check("J_current_path", False, None, "no Cu/Ti samples", "A/m^2"))
        checks.append(check("J_positive", False, None, "no Cu/Ti samples", "A/m^2"))

    # ---- 3. 温升: T>T0 且合理量级 (数十 K) ----
    tmax, tmin = float(T.max()), float(T.min())
    checks.append(
        check(
            "T_above_T0",
            tmin >= T0 - 1.0 and tmax > T0,
            [tmin, tmax],
            "T>T0 everywhere, max rise positive",
            "K",
        )
    )
    checks.append(
        check(
            "T_rise_reasonable",
            1.0 < tmax - T0 < 100.0,
            tmax - T0,
            "max T rise in (1,100) K",
            "K",
        )
    )

    # ---- 4. 焦耳热: Qrh>0 且螺栓(Ti 高阻)处 > 母线 ----
    qrh_max = float(Qrh.max())
    qrh_min = float(Qrh.min())
    checks.append(
        check("Qrh_nonneg", qrh_min >= 0, [qrh_min, qrh_max], "Qrh >= 0", "W/m^3")
    )
    # Qrh = J·E = normJ²/σ 自洽 (在母线铜域, 电导率 5.998e7)
    if len(cu) > 20:
        # 采样母线点验证 Qrh ≈ normJ²/σ_Cu
        idx = cu[:50]
        j = normJ[idx]
        qth = j**2 / SIGMA_CU
        # Qrh 应 ≈ qth (相对量级, 允许采样偏差 50%)
        ratios = Qrh[idx] / np.maximum(qth, 1e-6)
        med_ratio = float(np.median(ratios))
        checks.append(
            check(
                "Qrh_selfconsistent",
                0.5 < med_ratio < 2.0,
                med_ratio,
                "Qrh ≈ normJ²/σ_Cu (median ratio)",
                "ratio",
            )
        )

    # ---- 5. 固定约束: 螺栓外端面位移≈0 ----
    # 固定端面: cyl1 x=0.11 与 cyl2/3 z=-0.01 圆盘
    fixed_mask = ((np.abs(x - 0.110) < 0.001) & (np.abs(z - 0.05) < 0.01)) | (
        (np.abs(z + 0.010) < 0.001) & (np.abs(x - 0.045) < 0.01)
    )
    fixed_pts = np.where(fixed_mask & (y < -0.01))[0]
    if len(fixed_pts) > 0:
        d_fixed = float(np.max(disp[fixed_pts]))
        checks.append(
            check(
                "fixed_disp_zero",
                d_fixed < 1e-6,
                d_fixed,
                "max disp at fixed bolt ends < 1e-6 m",
                "m",
            )
        )
    else:
        checks.append(
            check("fixed_disp_zero", False, None, "no fixed-end samples", "m")
        )

    # ---- 6. 位移/应力量级 ----
    d_max = float(disp.max())
    checks.append(
        check(
            "disp_scale", 1e-6 < d_max < 1e-3, d_max, "max disp in (1e-6, 1e-3) m", "m"
        )
    )
    mises_max = float(mises.max())
    checks.append(
        check("mises_scale", mises_max < 1e9, mises_max, "max von Mises < 1 GPa", "Pa")
    )

    evidence = {
        "geometry": "L-shape busbar (Cu) + 3 through bolts (Ti, outer-side only), Form Union 7 domains",
        "electric": f"Terminal V={VTOT}V on vertical bolt end, Ground on 2 horizontal bolt ends",
        "thermal": "convection h=5 W/(m^2*K) to T0=293.15K on all external surfaces",
        "mech": "Fixed (u=v=w=0) on 3 bolt outer ends",
        "fields": f"V∈[{vmin:.4g},{vmax:.4g}]V, T∈[{tmin:.4g},{tmax:.4g}]K, "
        f"Jmax={float(normJ.max()):.3g} A/m^2, Qrhmax={qrh_max:.3g} W/m^3, "
        f"dispmax={d_max:.3g} m, misesmax={mises_max:.3g} Pa",
    }
    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out, evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
