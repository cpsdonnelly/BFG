import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon
import sys, os
plt.rcParams['font.family'] = 'DejaVu Sans'

W, H, DPI = 2240, 1580, 200
LW = 1.1
DASH = (0, (4, 2.5))


def fig(title=None):
    f = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)
    ax = f.add_axes([131 / W, 1 - 1449 / H, 1978 / W, 1318 / H])
    ax.set_xlim(0, 180); ax.set_ylim(120, 0); ax.axis('off')
    ax.add_patch(Rectangle((0, 0), 180, 120, fill=False, lw=LW, clip_on=False, zorder=3))
    if title:
        f.text(20 / W, 1 - 45 / H, title, fontsize=15, weight='bold', va='center', ha='left')
    return f, ax


def line(ax, *pts, lw=LW):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color='k', lw=lw, clip_on=False, solid_capstyle='projecting', zorder=3)


def box(ax, x0, y0, x1, y1, lw=LW):
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, lw=lw, clip_on=False, zorder=3))


def poly(ax, pts, lw=LW):
    ax.add_patch(Polygon(pts, closed=True, fill=False, lw=lw, clip_on=False, zorder=3))


def label(ax, x, y, s, size=22, bold=True, rot=0, ha='center', bg=False):
    kw = dict(fontsize=size, weight='bold' if bold else 'normal', rotation=rot, ha=ha, va='center',
              multialignment='center', clip_on=False, zorder=6, linespacing=1.15)
    if bg:
        kw['bbox'] = dict(facecolor='white', edgecolor='none', pad=1.5)
    ax.text(x, y, s, **kw)


def dim(ax, x1, y1, x2, y2, s, at=None, ha='center', rot=0, size=20):
    """Dashed double arrow with a label. at=(x,y) places the label; default mid-point on a white patch."""
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1), annotation_clip=False,
                arrowprops=dict(arrowstyle='<|-|>', ls=DASH, lw=0.9, color='k',
                                mutation_scale=12, shrinkA=0, shrinkB=0), zorder=4)
    if at is None:
        label(ax, (x1 + x2) / 2, (y1 + y2) / 2, s, size=size, bold=False, rot=rot, bg=True)
    else:
        label(ax, at[0], at[1], s, size=size, bold=False, rot=rot, ha=ha)


def arrow(ax, x1, y1, x2, y2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1), annotation_clip=False,
                arrowprops=dict(arrowstyle='-|>', lw=1.1, color='k', mutation_scale=14, shrinkA=0, shrinkB=0),
                zorder=4)


def objective(ax, x, y):
    ax.add_patch(Circle((x, y), 2.5, facecolor='white', edgecolor='k', lw=LW, zorder=5))
    ax.add_patch(Circle((x, y), 0.9, color='k', zorder=6))


def planet(ax, x, y, r=9.7, well=25.0):
    ax.add_patch(Circle((x, y), well, fill=False, ls=(0, (6, 4)), lw=1.0, zorder=2))
    ax.add_patch(Circle((x, y), r, facecolor='white', edgecolor='k', lw=LW, zorder=2))


def save(f, path):
    f.savefig(path, dpi=DPI)
    plt.close(f)
    from PIL import Image
    Image.open(path).convert('L').save(path)


OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
P = lambda n: os.path.join(OUT, f'image{n}.png')

# 1 Cruiser Clash
f, ax = fig()
box(ax, 45, 0, 135, 30); box(ax, 45, 90, 135, 120)
label(ax, 90, 19, 'FLEET A', size=28); label(ax, 90, 105, 'FLEET B', size=28)
dim(ax, 45, 6, 135, 6, '90cm')
dim(ax, 60, 30, 60, 90, '60cm')
save(f, P(1))

# 8 Navigate the Storm
f, ax = fig()
line(ax, (90, 0), (90, 120)); line(ax, (0, 60), (180, 60))
line(ax, (90, 10), (180, 10)); line(ax, (160, 0), (160, 60)); line(ax, (20, 60), (20, 120))
dim(ax, 0, -6, 90, -6, '90cm')
dim(ax, 95, 0, 95, 10, '10cm', at=(97, 5), ha='left')
dim(ax, -8.5, 60, -8.5, 120, '60cm', at=(-4.3, 90), rot=90)
dim(ax, 0, 112, 20, 112, '20cm')
label(ax, 125, 30, "Attacker's\nDeployment")
label(ax, 170, 35, 'Exit Point', rot=90)
label(ax, 55, 90, "Defender's\nDeployment")
save(f, P(8))

# 9 Destroy the Docks
f, ax = fig()
f.text(0.5, 1 - 65 / H, "DEFENDER'S REINFORCEMENT TABLE EDGE", fontsize=11, weight='bold', ha='center', va='center')
line(ax, (10, 0), (10, 120)); line(ax, (170, 0), (170, 120))
planet(ax, 90, 60)
label(ax, 90, 60, 'Planet'); label(ax, 90, 92, '30cm Gravity Well')
for x in (5, 175):
    label(ax, x, 45, "Attacker's Deployment", size=20, rot=90)
dim(ax, 0, 112, 10, 112, '10cm', at=(5, 96), rot=90)
dim(ax, 170, 112, 180, 112, '10cm', at=(175, 96), rot=90)
save(f, P(9))

# 13 Surprise Attack
f, ax = fig()
box(ax, 30, 30, 150, 90)
planet(ax, 90, 60)
label(ax, 90, 60, 'Planet')
label(ax, 48, 60, 'D3\nSQUADRONS\nON FULL\nALERT', size=17)
label(ax, 132, 60, 'STANDBY\nSHIPS WITHIN\n15cm OF\nPLANET', size=17)
dim(ax, 0, 60, 30, 60, '30cm')
dim(ax, 90, 0, 90, 30, '30cm', at=(91.5, 15), ha='left')
save(f, P(13))

# 14 Escalating Engagement
f, ax = fig()
box(ax, 30, 30, 150, 90)
label(ax, 90, 60, 'ENEMY MARKERS MAY NOT BE PLACED\nWITHIN 60cm OF EACH OTHER', size=18)
dim(ax, 90, 0, 90, 30, '30cm', at=(91.5, 15), ha='left')
dim(ax, 90, 90, 90, 120, '30cm', at=(91.5, 105), ha='left')
label(ax, -6, 60, '1', size=24); label(ax, 186, 60, '6', size=24)
label(ax, 90, -6, '2-3', size=24); label(ax, 90, 126, '4-5', size=24)
save(f, P(14))

# 15 Fleet Engagement A
f, ax = fig('FLEET ENGAGEMENT: SET-UP A')
line(ax, (30, 0), (30, 120)); line(ax, (150, 0), (150, 120))
box(ax, 60, 0, 120, 30); line(ax, (30, 30), (150, 30)); box(ax, 30, 90, 150, 120)
label(ax, 90, 19, "Defender's\nDeployment", size=20)
arrow(ax, 66, 4, 66, 14); arrow(ax, 114, 4, 114, 14)
dim(ax, 30, 6, 60, 6, '30cm'); dim(ax, 120, 6, 150, 6, '30cm')
dim(ax, 60, 36, 120, 36, '60cm')
dim(ax, 140, 30, 140, 90, '60cm', at=(138.5, 60), ha='right')
dim(ax, 40, 90, 40, 120, '30cm', at=(41.5, 113), ha='left')
label(ax, 90, 108, 'Div. 2', size=20); arrow(ax, 66, 116, 66, 106); arrow(ax, 114, 116, 114, 106)
label(ax, 15, 60, 'Div. 1', size=20); label(ax, 165, 60, 'Div. 3', size=20)
arrow(ax, 11, 46, 18, 39); label(ax, 15, 50, '45 deg', size=18, bold=False)
arrow(ax, 169, 46, 162, 39); label(ax, 165, 50, '45 deg', size=18, bold=False)
save(f, P(15))

# 16 Fleet Engagement B
f, ax = fig('FLEET ENGAGEMENT: SET-UP B')
f.text(1400 / W, 1 - 60 / H, "Opponent's Deployment", fontsize=22, weight='bold', ha='center', va='center')
f.text(0.5, 1 - 1525 / H, 'Your Deployment', fontsize=22, weight='bold', ha='center', va='center')
for x0 in (22.5, 67.5, 112.5):
    box(ax, x0, 0, x0 + 45, 30); box(ax, x0, 90, x0 + 45, 120)
for k, x0 in enumerate((22.5, 67.5, 112.5)):
    cx = x0 + 22.5
    label(ax, cx, 18, f'Div. {k + 1}', size=22); arrow(ax, cx - 3.5, 9, cx + 3.5, 9)
    label(ax, cx, 101, f'Div. {3 - k}', size=22); arrow(ax, cx + 3.5, 110, cx - 3.5, 110)
dim(ax, 67.5, 36, 112.5, 36, '45cm')
dim(ax, 9, 30, 9, 90, '60cm')
save(f, P(16))

# 17 Fleet Engagement C
f, ax = fig('FLEET ENGAGEMENT: SET-UP C')
line(ax, (30, 0), (30, 120)); line(ax, (150, 0), (150, 120))
box(ax, 60, 0, 120, 45)
label(ax, 90, 13, "Defender's\nDeployment", size=20)
arrow(ax, 66, 32, 66, 42); arrow(ax, 114, 32, 114, 42)
dim(ax, 90, 24, 90, 45, '45cm', at=(91.5, 35), ha='left')
dim(ax, 30, 52, 60, 52, '30cm'); dim(ax, 120, 52, 150, 52, '30cm')
label(ax, 15, 60, 'Div. 1', size=20); label(ax, 165, 60, 'Div. 2', size=20)
arrow(ax, 15, 80, 15, 70); arrow(ax, 165, 80, 165, 70)
dim(ax, 0, 112, 30, 112, '30cm'); dim(ax, 150, 112, 180, 112, '30cm')
save(f, P(17))

# 18 Fleet Engagement D
f, ax = fig('FLEET ENGAGEMENT: SET-UP D')
box(ax, 45, 0, 135, 30)
label(ax, 90, 18, "Defender's\nDeployment", size=20)
arrow(ax, 64, 5, 64, 15); arrow(ax, 116, 5, 116, 15)
dim(ax, 52, 0, 52, 30, '30cm', at=(53.5, 24), ha='left')
dim(ax, 0, 15, 45, 15, '45cm'); dim(ax, 135, 15, 180, 15, '45cm')
dim(ax, 90, 30, 90, 90, '60cm', at=(91.5, 60), ha='left')
for x0 in (0, 60, 120):
    box(ax, x0, 90, x0 + 60, 120)
    label(ax, x0 + 30, 99, f'Div. {x0 // 60 + 1}', size=20); arrow(ax, x0 + 30, 116, x0 + 30, 106)
dim(ax, 60, 84, 120, 84, '60cm')
save(f, P(18))

# 25 Ambush
f, ax = fig()
box(ax, 30, 30, 150, 90)
label(ax, 90, 60, 'Defending Player')
label(ax, 90, 15, 'Attacking Player (within 30cm of any edge)', size=18)
dim(ax, 8, 0, 8, 30, '30cm', at=(9.5, 15), ha='left')
dim(ax, 0, 105, 30, 105, '30cm')
save(f, P(25))

# 29 Warp Storm
f, ax = fig()
for (x0, y0), s in zip(((0, 0), (150, 0), (0, 90), (150, 90)),
                       ('Defending\nPlayer', 'Attacking\nPlayer', 'Attacking\nPlayer', 'Defending\nPlayer')):
    box(ax, x0, y0, x0 + 30, y0 + 30); label(ax, x0 + 15, y0 + 15, s, size=20)
dim(ax, 0, 35, 30, 35, '30cm')
dim(ax, 145, 0, 145, 30, '30cm', at=(143.5, 15), ha='right')
save(f, P(29))

# 31 Domination 1
f, ax = fig('DOMINATION 1')
line(ax, (0, 30), (180, 30)); line(ax, (0, 90), (180, 90))
label(ax, 90, 15, 'Attacking Player'); label(ax, 90, 105, 'Defending Player')
for x in (30, 90, 150):
    objective(ax, x, 60)
label(ax, 90, 51, 'Centre Objective', size=20)
dim(ax, 0, 60, 27.5, 60, '30cm', at=(14, 55))
dim(ax, 152.5, 60, 180, 60, '30cm', at=(166, 55))
dim(ax, 165, 0, 165, 30, '30cm', at=(163.5, 15), ha='right')
dim(ax, 165, 90, 165, 120, '30cm', at=(163.5, 105), ha='right')
save(f, P(31))

# 32 Domination 2
f, ax = fig('DOMINATION 2')
box(ax, 0, 0, 120, 30); box(ax, 60, 90, 180, 120)
label(ax, 60, 15, 'Attacking Player'); label(ax, 120, 105, 'Defending Player')
objective(ax, 150, 30); objective(ax, 30, 90); objective(ax, 90, 60)
label(ax, 90, 51, 'Centre Objective', size=20)
dim(ax, 120, 30, 147.5, 30, '30cm', at=(133.75, 35))
dim(ax, 152.5, 30, 180, 30, '30cm', at=(166.25, 35))
dim(ax, 150, 0, 150, 27.5, '30cm', at=(148.5, 13), ha='right')
label(ax, 166, 13, 'No\ndeployment', size=16)
dim(ax, 0, 90, 27.5, 90, '30cm', at=(13.75, 85))
dim(ax, 32.5, 90, 60, 90, '30cm', at=(46.25, 85))
dim(ax, 30, 92.5, 30, 120, '30cm', at=(31.5, 107), ha='left')
label(ax, 14, 107, 'No\ndeployment', size=16)
save(f, P(32))

# 33 Domination 3
f, ax = fig('DOMINATION 3')
poly(ax, [(135, 0), (135, 30), (150, 30), (150, 45), (180, 45), (180, 0)])
poly(ax, [(0, 75), (30, 75), (30, 90), (45, 90), (45, 120), (0, 120)])
for x, y in ((30, 30), (90, 30), (90, 90), (150, 90)):
    objective(ax, x, y)
dim(ax, 30, 0, 30, 27.5, '30cm', at=(31.5, 13), ha='left')
dim(ax, 90, 0, 90, 27.5, '30cm', at=(91.5, 13), ha='left')
dim(ax, 0, 30, 27.5, 30, '30cm', at=(14, 25))
dim(ax, 90, 92.5, 90, 120, '30cm', at=(91.5, 107), ha='left')
dim(ax, 150, 92.5, 150, 120, '30cm', at=(151.5, 107), ha='left')
dim(ax, 152.5, 90, 180, 90, '30cm', at=(166, 85))
dim(ax, 135, 3.5, 180, 3.5, '45cm')
dim(ax, 129, 0, 129, 45, '45cm', at=(127.5, 22), ha='right')
label(ax, 158, 21, 'Defending\nPlayer', size=20)
label(ax, 142.5, 38, '15cm', size=18, bold=False)
dim(ax, 0, 116.5, 45, 116.5, '45cm')
dim(ax, 51, 75, 51, 120, '45cm', at=(52.5, 97), ha='left')
label(ax, 21, 99, 'Attacking\nPlayer', size=20)
label(ax, 37.5, 82, '15cm', size=18, bold=False)
save(f, P(33))

# 35 Domination 5
f, ax = fig('DOMINATION 5')
line(ax, (45, 0), (45, 120)); line(ax, (135, 0), (135, 120))
label(ax, 22.5, 55, 'Attacking\nPlayer'); label(ax, 157.5, 55, 'Defending\nPlayer')
for x, y in ((90, 30), (90, 90), (120, 30), (60, 90)):
    objective(ax, x, y)
dim(ax, 90, 0, 90, 27.5, '30cm', at=(88.5, 13), ha='right')
dim(ax, 90, 92.5, 90, 120, '30cm', at=(91.5, 107), ha='left')
dim(ax, 120, 0, 120, 27.5, '30cm', at=(118.5, 13), ha='right')
dim(ax, 122.5, 30, 180, 30, '60cm', at=(151, 25))
dim(ax, 60, 92.5, 60, 120, '30cm', at=(61.5, 107), ha='left')
dim(ax, 0, 90, 57.5, 90, '60cm', at=(29, 85))
dim(ax, 0, 116.5, 45, 116.5, '45cm'); dim(ax, 135, 116.5, 180, 116.5, '45cm')
save(f, P(35))

# 36 Domination 6
f, ax = fig('DOMINATION 6')
line(ax, (45, 0), (45, 120)); line(ax, (135, 0), (135, 120))
label(ax, 22.5, 55, 'Attacking\nPlayer'); label(ax, 157.5, 55, 'Defending\nPlayer')
for y in (15, 60, 105):
    objective(ax, 90, y)
label(ax, 90, 69, 'Centre Objective', size=20)
dim(ax, 90, 0, 90, 12.5, '15cm', at=(91.5, 6), ha='left')
dim(ax, 90, 107.5, 90, 120, '15cm', at=(91.5, 114), ha='left')
dim(ax, 0, 116.5, 45, 116.5, '45cm'); dim(ax, 135, 116.5, 180, 116.5, '45cm')
save(f, P(36))
print('done')
