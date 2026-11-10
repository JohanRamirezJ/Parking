class Usuario {
  final int id;
  final String email;
  final String nombre;
  final String? telefono;
  final String? fotoPerfil;

  Usuario({required this.id, required this.email, required this.nombre, this.telefono, this.fotoPerfil});

  factory Usuario.fromJson(Map<String, dynamic> j) => Usuario(
        id: j['id'],
        email: j['email'],
        nombre: j['nombre'],
        telefono: j['telefono'],
        fotoPerfil: j['foto_perfil'],
      );
}

class Parqueadero {
  final int id;
  final String nombre;
  final String direccion;
  final double latitud;
  final double longitud;
  final String? horarioApertura;
  final String? horarioCierre;
  final bool? abiertoAhora;
  final int? capacidadTotal;
  final int? capacidadDisponible;
  final double? calificacion;
  final int totalResenas;
  final double? tarifaHora;
  final double? tarifaDia;
  final int? distanciaM;

  Parqueadero({
    required this.id,
    required this.nombre,
    required this.direccion,
    required this.latitud,
    required this.longitud,
    this.horarioApertura,
    this.horarioCierre,
    this.abiertoAhora,
    this.capacidadTotal,
    this.capacidadDisponible,
    this.calificacion,
    this.totalResenas = 0,
    this.tarifaHora,
    this.tarifaDia,
    this.distanciaM,
  });

  static double? _d(dynamic v) => v == null ? null : (v as num).toDouble();

  factory Parqueadero.fromJson(Map<String, dynamic> j) => Parqueadero(
        id: j['id'],
        nombre: j['nombre'],
        direccion: j['direccion'] ?? '',
        latitud: _d(j['latitud'])!,
        longitud: _d(j['longitud'])!,
        horarioApertura: j['horario_apertura'],
        horarioCierre: j['horario_cierre'],
        abiertoAhora: j['abierto_ahora'],
        capacidadTotal: j['capacidad_total'],
        capacidadDisponible: j['capacidad_disponible_estimada'],
        calificacion: _d(j['calificacion_promedio']),
        totalResenas: j['total_resenas'] ?? 0,
        tarifaHora: _d(j['tarifa_hora']),
        tarifaDia: _d(j['tarifa_dia']),
        distanciaM: (j['distancia_m'] as num?)?.round(),
      );

  String get horario {
    if (horarioApertura == null || horarioCierre == null) return 'Horario no disponible';
    if (horarioApertura == horarioCierre) return 'Abierto 24 horas';
    return '$horarioApertura – $horarioCierre';
  }
}

class Resena {
  final int id;
  final String autor;
  final int calificacion;
  final String? comentario;
  final DateTime fecha;

  Resena({required this.id, required this.autor, required this.calificacion, this.comentario, required this.fecha});

  factory Resena.fromJson(Map<String, dynamic> j) => Resena(
        id: j['id'],
        autor: j['usuario']['nombre'],
        calificacion: j['calificacion'],
        comentario: j['comentario'],
        fecha: DateTime.parse(j['fecha']),
      );
}

class Destino {
  final String nombre;
  final double latitud;
  final double longitud;
  Destino(this.nombre, this.latitud, this.longitud);
}

/// Resultado del módulo de IA multicriterio.
class CriterioEvaluado {
  final String clave;
  final String texto;
  final double puntaje; // 0–1
  final double peso;
  final double pesoPct;
  final double aporte; // puntos sobre 100
  final bool estimado;

  CriterioEvaluado(this.clave, this.texto, this.puntaje, this.peso, this.pesoPct, this.aporte, this.estimado);

  factory CriterioEvaluado.fromJson(String clave, Map<String, dynamic> j) => CriterioEvaluado(
        clave,
        j['texto'] ?? '',
        (j['puntaje'] as num).toDouble(),
        (j['peso'] as num).toDouble(),
        (j['peso_pct'] as num).toDouble(),
        (j['aporte'] as num).toDouble(),
        j['estimado'] == true,
      );
}

class OpcionRecomendada {
  final int posicion;
  final double puntaje;
  final Parqueadero parqueadero;
  final List<CriterioEvaluado> criterios;
  final int costoTotal;
  final List<String> alertas;
  final String justificacion;

  OpcionRecomendada(this.posicion, this.puntaje, this.parqueadero, this.criterios, this.costoTotal, this.alertas,
      this.justificacion);

  factory OpcionRecomendada.fromJson(Map<String, dynamic> j) {
    final c = Map<String, dynamic>.from(j['criterios']);
    return OpcionRecomendada(
      j['posicion'],
      (j['puntaje'] as num).toDouble(),
      Parqueadero.fromJson(Map<String, dynamic>.from(j['parqueadero'])),
      [for (final e in c.entries) CriterioEvaluado.fromJson(e.key, Map<String, dynamic>.from(e.value))],
      (j['costo_total_estimado'] as num).round(),
      List<String>.from(j['alertas'] ?? const []),
      j['justificacion'] ?? '',
    );
  }
}

class Recomendacion {
  final String perfil;
  final Map<String, double> pesos;
  final double horas;
  final List<OpcionRecomendada> resultados;
  final String? mensaje;

  Recomendacion(this.perfil, this.pesos, this.horas, this.resultados, this.mensaje);

  factory Recomendacion.fromJson(Map<String, dynamic> j) => Recomendacion(
        j['perfil'] ?? '',
        Map<String, dynamic>.from(j['pesos']).map((k, v) => MapEntry(k, (v as num).toDouble())),
        (j['horas'] as num).toDouble(),
        [for (final r in j['resultados'] as List) OpcionRecomendada.fromJson(Map<String, dynamic>.from(r))],
        j['mensaje'],
      );
}
