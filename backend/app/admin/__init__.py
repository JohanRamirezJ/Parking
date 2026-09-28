"""Panel web de administración (Jinja2) — HU 14, RF-09, RF-10, RF-11, RF-13."""
import csv
import io
import json
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import (Blueprint, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from sqlalchemy import func, select

from ..extensions import db
from ..models import (ConsultaIA, EventoBusqueda, LogAuditoria, Notificacion, Parqueadero,
                      ReporteUsuario, Resena, Usuario)
from ..services.directorio import aplicar_datos, auditar, snapshot
from ..services.validacion import validar_parqueadero

admin_bp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="../templates")


# ---------------- sesión y seguridad ----------------
def admin_requerido(fn):
    @wraps(fn)
    def envoltura(*a, **kw):
        uid = session.get("admin_id")
        u = db.session.get(Usuario, uid) if uid else None
        if not u or not u.es_admin or not u.activo:
            session.clear()
            return redirect(url_for("admin.login", siguiente=request.path))
        g.admin = u
        return fn(*a, **kw)
    return envoltura


def _csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@admin_bp.before_request
def _verificar_csrf():
    if request.method == "POST":
        if not session.get("csrf") or request.form.get("csrf") != session.get("csrf"):
            abort(400, "Token CSRF inválido. Recarga la página.")


@admin_bp.app_context_processor
def _ctx():
    return {"csrf_token": _csrf_token}


@admin_bp.app_template_filter("cop")
def _cop(v):
    return "—" if v is None else "$" + f"{v:,.0f}".replace(",", ".")


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = db.session.scalar(select(Usuario).where(Usuario.email == email))
        if u and u.es_admin and u.activo and u.check_password(request.form.get("password", "")):
            session.clear()
            session["admin_id"] = u.id
            u.ultimo_acceso = datetime.utcnow()
            db.session.commit()
            destino = request.args.get("siguiente", "")
            return redirect(destino if destino.startswith("/admin") else url_for("admin.dashboard"))
        flash("Credenciales inválidas o sin permisos de administrador", "error")
    return render_template("admin/login.html")


@admin_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


# ---------------- dashboard analítico ----------------
def _rango_fechas():
    hoy = datetime.utcnow().date()
    try:
        desde = datetime.strptime(request.args.get("desde", ""), "%Y-%m-%d").date()
    except ValueError:
        desde = hoy - timedelta(days=29)
    try:
        hasta = datetime.strptime(request.args.get("hasta", ""), "%Y-%m-%d").date()
    except ValueError:
        hasta = hoy
    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


def _metricas(desde, hasta) -> dict:
    ini = datetime.combine(desde, datetime.min.time())
    fin = datetime.combine(hasta, datetime.max.time())

    activos = db.session.scalars(select(Parqueadero).where(Parqueadero.activo.is_(True))).all()
    n_activos = len(activos)
    con_tarifa = sum(1 for p in activos if p.tarifa_hora is not None or p.tarifa_dia is not None)
    con_resena = sum(1 for p in activos if p.total_resenas() > 0)

    busq_dia = dict(db.session.execute(
        select(func.date(EventoBusqueda.fecha), func.count())
        .where(EventoBusqueda.fecha.between(ini, fin)).group_by(func.date(EventoBusqueda.fecha))).all())
    dias, serie_busq = [], []
    d = desde
    while d <= hasta:
        dias.append(d.strftime("%d/%m"))
        serie_busq.append(busq_dia.get(d.isoformat(), 0) or busq_dia.get(d, 0))
        d += timedelta(days=1)

    resenas = db.session.scalars(select(Resena).where(Resena.fecha.between(ini, fin),
                                                      Resena.estado == "aprobada")).all()
    dist_cal = [sum(1 for r in resenas if r.calificacion == i) for i in range(1, 6)]

    rangos = [(0, 3000), (3000, 5000), (5000, 7000), (7000, 10000), (10000, None)]
    etiquetas_tarifa = ["< $3.000", "$3.000–5.000", "$5.000–7.000", "$7.000–10.000", "> $10.000"]
    tarifas = [p.tarifa_hora for p in activos if p.tarifa_hora is not None]
    dist_tarifa = [sum(1 for t in tarifas if t >= a and (b is None or t < b)) for a, b in rangos]

    ocupacion = []
    for p in activos:
        if p.capacidad_total:
            libre = p.capacidad_disponible_estimada or 0
            ocupacion.append((p.nombre, round(100 * (p.capacidad_total - libre) / p.capacidad_total)))
    ocupacion.sort(key=lambda x: -x[1])

    top_chat = db.session.execute(
        select(Parqueadero.nombre, func.count(ConsultaIA.id))
        .join(ConsultaIA, ConsultaIA.parqueadero_recomendado_id == Parqueadero.id)
        .where(ConsultaIA.fecha.between(ini, fin))
        .group_by(Parqueadero.nombre).order_by(func.count(ConsultaIA.id).desc()).limit(5)).all()

    total_busq = sum(serie_busq)
    return {
        "desde": desde, "hasta": hasta,
        "kpi": {
            "parqueaderos_activos": n_activos,
            "usuarios": db.session.scalar(select(func.count(Usuario.id)).where(Usuario.es_admin.is_(False))),
            "busquedas": total_busq,
            "resenas": len(resenas),
            "consultas_ia": db.session.scalar(select(func.count(ConsultaIA.id)).where(ConsultaIA.fecha.between(ini, fin))),
            "cobertura_tarifas": round(100 * con_tarifa / n_activos) if n_activos else 0,
            "cobertura_resenas": round(100 * con_resena / n_activos) if n_activos else 0,
            "reportes_pendientes": db.session.scalar(select(func.count(ReporteUsuario.id)).where(ReporteUsuario.estado == "pendiente")),
            "tarifa_promedio_hora": round(sum(tarifas) / len(tarifas)) if tarifas else None,
        },
        "graficas": {
            "busquedas": {"labels": dias, "data": serie_busq, "vacio": total_busq == 0},
            "calificaciones": {"labels": ["1★", "2★", "3★", "4★", "5★"], "data": dist_cal, "vacio": not resenas},
            "tarifas": {"labels": etiquetas_tarifa, "data": dist_tarifa, "vacio": not tarifas},
            "ocupacion": {"labels": [o[0] for o in ocupacion[:8]], "data": [o[1] for o in ocupacion[:8]],
                          "vacio": not ocupacion},
        },
        "top_chat": top_chat,
    }


@admin_bp.get("/")
@admin_requerido
def dashboard():
    desde, hasta = _rango_fechas()
    m = _metricas(desde, hasta)
    return render_template("admin/dashboard.html", m=m, graficas_json=json.dumps(m["graficas"], ensure_ascii=False))


@admin_bp.get("/exportar.csv")
@admin_requerido
def exportar():
    """Exportación compatible con Excel (CSV UTF-8 con BOM). Para PDF: botón Imprimir del dashboard."""
    desde, hasta = _rango_fechas()
    m = _metricas(desde, hasta)
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Reporte SmartPark", f"{desde} a {hasta}"])
    w.writerow([])
    w.writerow(["Indicador", "Valor"])
    for k, v in m["kpi"].items():
        w.writerow([k.replace("_", " "), v if v is not None else ""])
    w.writerow([])
    w.writerow(["Parqueadero", "Dirección", "Tarifa hora", "Tarifa día", "Calificación", "Reseñas",
                "Capacidad", "Disponibles (est.)", "Activo"])
    for p in db.session.scalars(select(Parqueadero).order_by(Parqueadero.nombre)).all():
        w.writerow([p.nombre, p.direccion, p.tarifa_hora or "", p.tarifa_dia or "",
                    p.calificacion_promedio or "", p.total_resenas(), p.capacidad_total or "",
                    p.capacidad_disponible_estimada or "", "sí" if p.activo else "no"])
    nombre = f"smartpark_reporte_{desde}_{hasta}.csv"
    return Response(buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={nombre}"})


# ---------------- directorio de parqueaderos ----------------
@admin_bp.get("/parqueaderos")
@admin_requerido
def parqueaderos():
    q = request.args.get("q", "").strip()
    stmt = select(Parqueadero).order_by(Parqueadero.nombre)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Parqueadero.nombre.ilike(like) | Parqueadero.direccion.ilike(like))
    return render_template("admin/parqueaderos.html", parqueaderos=db.session.scalars(stmt).all(), q=q)


def _num(v):
    return "" if v is None else (int(v) if float(v).is_integer() else v)


def _form_desde(p: Parqueadero | None) -> dict:
    if not p:
        return {"activo": True}
    return {"nombre": p.nombre, "direccion": p.direccion, "latitud": p.latitud, "longitud": p.longitud,
            "tarifa_hora": _num(p.tarifa_hora), "tarifa_dia": _num(p.tarifa_dia),
            "horario_apertura": p.horario_apertura.strftime("%H:%M") if p.horario_apertura else "",
            "horario_cierre": p.horario_cierre.strftime("%H:%M") if p.horario_cierre else "",
            "capacidad_total": p.capacidad_total or "", "capacidad_disponible_estimada":
                p.capacidad_disponible_estimada if p.capacidad_disponible_estimada is not None else "",
            "imagen_url": p.imagen_url or "", "activo": p.activo}


@admin_bp.route("/parqueaderos/nuevo", methods=["GET", "POST"])
@admin_bp.route("/parqueaderos/<int:pid>/editar", methods=["GET", "POST"])
@admin_requerido
def editar_parqueadero(pid: int | None = None):
    p = db.session.get(Parqueadero, pid) if pid else None
    if pid and not p:
        abort(404)
    datos, errores = _form_desde(p), {}
    if request.method == "POST":
        datos = request.form.to_dict()
        datos["activo"] = "activo" in request.form
        limpio, errores = validar_parqueadero(datos)
        if not errores:
            previos = snapshot(p) if p else None
            nuevo = p is None
            if nuevo:
                p = Parqueadero()
                db.session.add(p)
            aplicar_datos(p, limpio)
            db.session.flush()
            auditar(g.admin.id, "CREATE" if nuevo else "UPDATE", "parqueadero", p.id, previos, snapshot(p))
            db.session.commit()
            flash(f"Parqueadero «{p.nombre}» {'creado' if nuevo else 'actualizado'}", "ok")
            return redirect(url_for("admin.parqueaderos"))
        flash("No se guardó: revisa los campos marcados", "error")
    return render_template("admin/parqueadero_form.html", p=p, datos=datos, errores=errores)


@admin_bp.post("/parqueaderos/<int:pid>/estado")
@admin_requerido
def cambiar_estado(pid: int):
    p = db.session.get(Parqueadero, pid) or abort(404)
    previos = snapshot(p)
    p.activo = not p.activo
    auditar(g.admin.id, "UPDATE", "parqueadero", p.id, previos, snapshot(p))
    db.session.commit()
    flash(f"«{p.nombre}» {'activado' if p.activo else 'desactivado'}", "ok")
    return redirect(url_for("admin.parqueaderos"))


@admin_bp.post("/parqueaderos/<int:pid>/eliminar")
@admin_requerido
def eliminar_parqueadero(pid: int):
    p = db.session.get(Parqueadero, pid) or abort(404)
    previos, nombre = snapshot(p), p.nombre
    for r in p.resenas:
        for rep in db.session.scalars(select(ReporteUsuario).where(ReporteUsuario.resena_id == r.id)):
            rep.resena_id = None
    from ..models import Visita
    for v in db.session.scalars(select(Visita).where(Visita.parqueadero_id == pid)):
        db.session.delete(v)
    for c in db.session.scalars(select(ConsultaIA).where(ConsultaIA.parqueadero_recomendado_id == pid)):
        c.parqueadero_recomendado_id = None
    db.session.delete(p)
    auditar(g.admin.id, "DELETE", "parqueadero", pid, previos, None)
    db.session.commit()
    flash(f"«{nombre}» eliminado", "ok")
    return redirect(url_for("admin.parqueaderos"))


# ---------------- usuarios reportados ----------------
@admin_bp.get("/reportes")
@admin_requerido
def reportes():
    estado = request.args.get("estado", "pendiente")
    stmt = select(ReporteUsuario).order_by(ReporteUsuario.fecha_reporte.desc())
    if estado != "todos":
        stmt = stmt.where(ReporteUsuario.estado == estado)
    return render_template("admin/reportes.html", reportes=db.session.scalars(stmt).all(), estado=estado)


@admin_bp.post("/reportes/<int:rid>/accion")
@admin_requerido
def accion_reporte(rid: int):
    rep = db.session.get(ReporteUsuario, rid) or abort(404)
    accion = request.form.get("accion")
    obs = request.form.get("observaciones", "").strip() or None
    u = rep.usuario_reportado
    previos = json.dumps({"estado": rep.estado, "usuario_activo": u.activo})

    if accion == "advertir":
        u.advertencias += 1
        rep.estado = "resuelto"
        msg = "Recibiste una advertencia por una reseña que incumple las normas de la comunidad."
    elif accion == "suspender":
        u.activo = False
        rep.estado = "resuelto"
        if rep.resena:
            rep.resena.estado = "rechazada"
            rep.resena.parqueadero.recalcular_promedio()
        msg = "Tu cuenta fue suspendida por incumplir las normas de la comunidad."
    elif accion == "descartar":
        rep.estado = "descartado"
        msg = None
    else:
        abort(400, "Acción inválida")

    rep.fecha_resolucion = datetime.utcnow()
    rep.observaciones_admin = obs
    if msg:  # RF-10: notificar al usuario reportado
        db.session.add(Notificacion(usuario_id=u.id, mensaje=msg + (f" Nota: {obs}" if obs else "")))
    auditar(g.admin.id, "UPDATE", "usuario", u.id, previos,
            json.dumps({"accion": accion, "estado": rep.estado, "usuario_activo": u.activo}))
    db.session.commit()
    flash(f"Reporte #{rep.id}: acción «{accion}» aplicada", "ok")
    return redirect(url_for("admin.reportes"))


# ---------------- auditoría ----------------
@admin_bp.get("/auditoria")
@admin_requerido
def auditoria():
    logs = db.session.scalars(select(LogAuditoria).order_by(LogAuditoria.fecha.desc()).limit(200)).all()
    return render_template("admin/auditoria.html", logs=logs)
