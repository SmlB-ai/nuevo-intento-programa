import random
import os
from collections import defaultdict
from datetime import datetime, timedelta

class Scheduler:
    def __init__(self, config, participants_data, history_data):
        self.year = int(config['year'])
        self.month = int(config['month'])
        self.weeks_config = config['weeks']
        self.participants_by_role = self._prepare_participants(participants_data)

        # Historial mejorado
        self.history_by_role, self.history_any_role = self._prepare_history(history_data)

        # Rastreadores para el mes actual
        self.special_roles_assigned_this_month = set()
        self.SPECIAL_ROLES = {'Lectura de la biblia', 'Seamos mejores maestros', 'Acomodadores'}

        self.schedule = {i: {} for i in range(len(self.weeks_config))}

    def _prepare_participants(self, participants_raw):
        # ... (sin cambios)
        participants = defaultdict(list)
        for p in participants_raw:
            participants[p['nombre_rol']].append(p)
            if p['nombre_rol'] == 'Seamos mejores maestros':
                participants[f"smm_{p['genero']}"].append(p)
            if p['nombre_rol'] == 'Acomodadores':
                participants[f"acomodadores_{p['grupo_edad']}"].append(p)
        return participants

    def _prepare_history(self, history_raw):
        history_by_role = defaultdict(lambda: defaultdict(lambda: '1970-01-01'))
        history_any_role = defaultdict(lambda: '1970-01-01')

        for record in history_raw:
            person_id = record['persona_id']
            date_str = f"{record['anio']}-{record['mes']:02d}-{record['semana']:02d}"

            # Guardar la fecha más reciente para un rol específico
            role_key = self.get_history_key(record['asignacion_nombre'], record.get('rol_secundario'))
            if date_str > history_by_role[person_id][role_key]:
                history_by_role[person_id][role_key] = date_str

            # Guardar la fecha más reciente para CUALQUIER rol
            if date_str > history_any_role[person_id]:
                history_any_role[person_id] = date_str

        return history_by_role, history_any_role

    def get_history_key(self, role_name, sub_role=None):
        # ... (sin cambios)
        return f"{role_name}{f'_{sub_role}' if sub_role else ''}"

    def find_candidate(self, role_key, role_name_for_history, assigned_this_week, sub_role_key=None, custom_exclusions=None):
        candidates = self.participants_by_role.get(role_key, [])
        if not candidates:
            return {"nombre": "PENDIENTE", "persona_id": None}

        history_key = self.get_history_key(role_name_for_history, sub_role_key)
        exclusions = set(assigned_this_week)
        if custom_exclusions:
            exclusions.update(custom_exclusions)

        eligible = []
        for p in candidates:
            if p['persona_id'] not in exclusions:
                # Puntuación mejorada: (1. última vez CUALQUIER asignación, 2. última vez ESTA asignación, 3. aleatorio)
                last_any = self.history_any_role[p['persona_id']]
                last_this_role = self.history_by_role[p['persona_id']][history_key]
                score = (
                    datetime.strptime(last_any, '%Y-%m-%d'),
                    datetime.strptime(last_this_role, '%Y-%m-%d'),
                    random.random()
                )
                eligible.append((score, p))

        if not eligible:
            return {"nombre": "FALTAN CANDIDATOS", "persona_id": None}

        eligible.sort(key=lambda x: x[0])
        return eligible[0][1]

    def _assign_week(self, week_index, week_config):
        assigned_this_week = set()
        week_schedule = defaultdict(list)
        current_date_str = f"{self.year}-{self.month:02d}-{week_index+1:02d}"

        def assign_and_get_person(role_key, role_name, sub_role=None, is_special_role=False):
            exclusions = self.special_roles_assigned_this_month if is_special_role else None
            candidate = self.find_candidate(role_key, role_name, assigned_this_week, sub_role, custom_exclusions=exclusions)
            if candidate and candidate.get('persona_id'):
                person_id = candidate['persona_id']
                assigned_this_week.add(person_id)
                history_key = self.get_history_key(role_name, sub_role)
                self.history_by_role[person_id][history_key] = current_date_str
                self.history_any_role[person_id] = current_date_str
                if is_special_role:
                    self.special_roles_assigned_this_month.add(person_id)
            return candidate

        # --- REGLA DE EXCLUSIVIDAD: Asignar Presidente PRIMERO y bloquearlo ---
        president_person = assign_and_get_person("Presidente", "Presidente", sub_role=None, is_special_role=False)
        week_schedule["Presidente"].append({"key": "Presidente_0", **president_person})

        # Lógica de asignación para el resto de los roles
        assignments_to_make = {
            "Oracion_Inicial": [("Oraciones", "Oracion", "inicial", False)],
            "Tesoros": [("Tesoros", "Tesoros", None, False)],
            "Perlas": [("Perlas", "Perlas", None, False)],
            "Vida_Ministerio_1": [("Vida y ministerio", "Vida y ministerio", "vm1", False)],
            "Estudio_Libro": [("Estudio del libro", "Estudio del libro", None, False)],
            "Lector_Libro": [("Lector del libro", "Lector del libro", None, False)],
            "Oracion_Final": [("Oraciones", "Oracion", "final", False)],
            # Asignaciones especiales
            "Lectura_Biblia": [("Lectura de la biblia", "Lectura de la biblia", "sala_a", True), ("Lectura de la biblia", "Lectura de la biblia", "sala_b", True)],
            "Acomodadores_Entrada": [("acomodadores_adulto", "Acomodadores", "entrada", True)] * 3,
            "Acomodadores_Auditorio": [("Acomodadores", "Acomodadores", "auditorio", True)] * 2,
        }
        if week_config.get('vym2_presente'):
            assignments_to_make["Vida_Ministerio_2"] = [("Vida y ministerio", "Vida y ministerio", "vm2", False)]
        if week_config.get('vym3_presente'):
            assignments_to_make["Vida_Ministerio_3"] = [("Vida y ministerio", "Vida y ministerio", "vm3", False)]

        for key, parts in assignments_to_make.items():
            for i, (role_key, role_name, sub_role, is_special) in enumerate(parts):
                slot_key = f"{key}_{i}"
                person = assign_and_get_person(role_key, role_name, sub_role, is_special)
                week_schedule[key].append({"key": slot_key, **person})

        # Seamos Mejores Maestros (es un rol especial)
        smm_count = int(week_config.get('smm_count', 0))
        for i in range(1, smm_count + 1):
            part_config = week_config[f'smm_part_{i}']
            role_key = f"smm_{part_config['genero']}"

            for sala in ['A', 'B']:
                key = f"SMM_{i}_{sala}"
                sub_role_sala = f"sala_{sala.lower()}"

                if part_config['tipo'] == 'demostracion':
                    p1 = assign_and_get_person(role_key, 'Seamos mejores maestros', f'principal_{sub_role_sala}', is_special_role=True)
                    p2 = assign_and_get_person(role_key, 'Seamos mejores maestros', f'ayudante_{sub_role_sala}', is_special_role=True)
                    week_schedule[key].append({"key": f"{key}_principal", **p1})
                    week_schedule[key].append({"key": f"{key}_ayudante", **p2})
                else: # persona sola
                    p1 = assign_and_get_person(role_key, 'Seamos mejores maestros', f'principal_{sub_role_sala}', is_special_role=True)
                    week_schedule[key].append({"key": f"{key}_principal", **p1})

        self.schedule[week_index] = week_schedule

    def generate_schedule(self):
        for i, week_config in enumerate(self.weeks_config):
            if not week_config.get('is_cancelled', False):
                self._assign_week(i, week_config)

        output = {"weeks": []}
        assignment_order = [
            ("Presidente", "Presidente"), ("Oracion_Inicial", "Oración Inicial"),
            # ... (resto del orden de asignaciones sin cambios)
            ("Tesoros", "Tesoros de la Biblia"), ("Perlas", "Perlas Escondidas"),
            ("Lectura_Biblia", "Lectura Bíblica"),
            ("SMM_1_A", "Mejores Maestros 1 (Sala A)"), ("SMM_1_B", "Mejores Maestros 1 (Sala B)"),
            ("SMM_2_A", "Mejores Maestros 2 (Sala A)"), ("SMM_2_B", "Mejores Maestros 2 (Sala B)"),
            ("SMM_3_A", "Mejores Maestros 3 (Sala A)"), ("SMM_3_B", "Mejores Maestros 3 (Sala B)"),
            ("SMM_4_A", "Mejores Maestros 4 (Sala A)"), ("SMM_4_B", "Mejores Maestros 4 (Sala B)"),
            ("Vida_Ministerio_1", "Vida y Ministerio 1"), ("Vida_Ministerio_2", "Vida y Ministerio 2"),
            ("Vida_Ministerio_3", "Vida y Ministerio 3"),
            ("Estudio_Libro", "Estudio Bíblico"), ("Lector_Libro", "Lector del Estudio"),
            ("Oracion_Final", "Oración Final"),
            ("Acomodadores_Entrada", "Acomodadores (Entrada)"),
            ("Acomodadores_Auditorio", "Acomodadores (Auditorio)")
        ]

        for i, week_config in enumerate(self.weeks_config):
            # --- Cálculo de fecha de Viernes a Jueves ---
            first_day_of_month = datetime(self.year, self.month, 1)
            FRIDAY = 4 # 0=Lunes, 4=Viernes
            days_since_friday = (first_day_of_month.weekday() - FRIDAY + 7) % 7
            first_friday = first_day_of_month - timedelta(days=days_since_friday)
            if first_friday.month != self.month:
                first_friday += timedelta(weeks=1)

            start_of_week = first_friday + timedelta(weeks=i)
            end_of_week = start_of_week + timedelta(days=6)

            date_format = lambda d: d.strftime('%#d de %b' if os.name == 'nt' else '%-d de %b')
            week_date_str = f"{date_format(start_of_week)} - {date_format(end_of_week)}"

            week_data = {"week_index": i, "week_date": week_date_str, "assignments": []}

            if week_config.get('is_cancelled', False):
                week_data["is_cancelled"] = True
                week_data["cancel_reason"] = week_config.get('cancel_reason')
            else:
                weekly_schedule = self.schedule.get(i, {})
                for key, title in assignment_order:
                    if key in weekly_schedule and weekly_schedule[key]:
                        slots = weekly_schedule[key]
                        week_data["assignments"].append({"key": key, "title": title, "slots": slots})

            output["weeks"].append(week_data)

        return output