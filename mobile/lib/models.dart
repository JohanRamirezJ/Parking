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
