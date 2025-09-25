import random
from collections import defaultdict
from datetime import datetime, timedelta

class Scheduler:
    def __init__(self, config, participants_data, history_data):
        self.year = int(config['year'])
        self.month = int(config['month'])
        self.weeks_config = config['weeks']
        self.participants_by_role = self._prepare_participants(participants_data)
        self.history = self._prepare_history(history_data)
        self.schedule = {i: {} for i in range(len(self.weeks_config))}
        self.smm_assigned_this_month = set()

    def _prepare_participants(self, participants_raw):
        participants = defaultdict(list)
        for p in participants_raw:
            participants[p['nombre_rol']].append(p)
            if p['nombre_rol'] == 'Seamos mejores maestros':
                participants[f"smm_{p['genero']}"].append(p)
            if p['nombre_rol'] == 'Acomodadores':
                participants[f"acomodadores_{p['grupo_edad']}"].append(p)
        return participants

    def _prepare_history(self, history_raw):
        history = defaultdict(lambda: defaultdict(lambda: '1970-01-01'))
        for record in history_raw:
            key = self.get_history_key(record['asignacion_nombre'], record.get('rol_secundario'))
            date_str = f"{record['anio']}-{record['mes']:02d}-{record['semana']:02d}"
            if date_str > history[record['persona_id']][key]:
                history[record['persona_id']][key] = date_str
        return history

    def get_history_key(self, role_name, sub_role=None):
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
                last_assigned = self.history[p['persona_id']][history_key]
                score = (datetime.strptime(last_assigned, '%Y-%m-%d'), random.random())
                eligible.append((score, p))

        if not eligible:
            return {"nombre": "FALTAN CANDIDATOS", "persona_id": None}

        eligible.sort(key=lambda x: x[0])
        return eligible[0][1]

    def _assign_week(self, week_index, week_config):
        assigned_this_week = set()
        week_schedule = defaultdict(list)

        def assign_and_get_person(role_key, role_name, sub_role=None, custom_exclusions=None):
            candidate = self.find_candidate(role_key, role_name, assigned_this_week, sub_role, custom_exclusions)
            if candidate and candidate.get('persona_id'):
                assigned_this_week.add(candidate['persona_id'])
                history_key = self.get_history_key(role_name, sub_role)
                self.history[candidate['persona_id']][history_key] = f"{self.year}-{self.month:02d}-{week_index+1:02d}"
            return candidate

        # Define all assignments with unique keys
        assignments_to_make = {
            "Presidente": [("Presidente", "Presidente", None)],
            "Oracion_Inicial": [("Oraciones", "Oracion", "inicial")],
            "Tesoros": [("Tesoros", "Tesoros", None)],
            "Perlas": [("Perlas", "Perlas", None)],
            "Lectura_Biblia": [("Lectura de la biblia", "Lectura de la biblia", "sala_a"), ("Lectura de la biblia", "Lectura de la biblia", "sala_b")],
            "Vida_Ministerio_1": [("Vida y ministerio", "Vida y ministerio", "vm1")],
            "Estudio_Libro": [("Estudio del libro", "Estudio del libro", None)],
            "Lector_Libro": [("Lector del libro", "Lector del libro", None)],
            "Oracion_Final": [("Oraciones", "Oracion", "final")],
            "Acomodadores_Entrada": [("acomodadores_adulto", "Acomodadores", "entrada")] * 3,
            "Acomodadores_Auditorio": [("Acomodadores", "Acomodadores", "auditorio")] * 2,
        }
        if week_config.get('vym2_presente'):
            assignments_to_make["Vida_Ministerio_2"] = [("Vida y ministerio", "Vida y ministerio", "vm2")]
        if week_config.get('vym3_presente'):
            assignments_to_make["Vida_Ministerio_3"] = [("Vida y ministerio", "Vida y ministerio", "vm3")]

        for key, parts in assignments_to_make.items():
            for i, (role_key, role_name, sub_role) in enumerate(parts):
                slot_key = f"{key}_{i}"
                person = assign_and_get_person(role_key, role_name, sub_role)
                week_schedule[key].append({"key": slot_key, **person})

        # Seamos Mejores Maestros (dos salas, A y B)
        smm_count = int(week_config.get('smm_count', 0))
        for i in range(1, smm_count + 1):
            part_config = week_config[f'smm_part_{i}']
            role_key = f"smm_{part_config['genero']}"

            for sala in ['A', 'B']:
                key = f"SMM_{i}_{sala}"
                sub_role_sala = f"sala_{sala.lower()}"

                if part_config['tipo'] == 'demostracion':
                    p1 = assign_and_get_person(role_key, 'Seamos mejores maestros', f'principal_{sub_role_sala}', self.smm_assigned_this_month)
                    if p1.get('persona_id'): self.smm_assigned_this_month.add(p1['persona_id'])

                    current_exclusions = self.smm_assigned_this_month.union({p1.get('persona_id')})
                    p2 = assign_and_get_person(role_key, 'Seamos mejores maestros', f'ayudante_{sub_role_sala}', current_exclusions)
                    if p2.get('persona_id'): self.smm_assigned_this_month.add(p2['persona_id'])

                    week_schedule[key].append({"key": f"{key}_principal", **p1})
                    week_schedule[key].append({"key": f"{key}_ayudante", **p2})
                else: # persona sola
                    p1 = assign_and_get_person(role_key, 'Seamos mejores maestros', f'principal_{sub_role_sala}', self.smm_assigned_this_month)
                    if p1.get('persona_id'): self.smm_assigned_this_month.add(p1['persona_id'])
                    week_schedule[key].append({"key": f"{key}_principal", **p1})

        self.schedule[week_index] = week_schedule

    def generate_schedule(self):
        for i, week_config in enumerate(self.weeks_config):
            self._assign_week(i, week_config)

        output = {"weeks": []}
        assignment_order = [
            ("Presidente", "Presidente"), ("Oracion_Inicial", "Oración Inicial"),
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

        for i, weekly_schedule in self.schedule.items():
            # Obtener la fecha de inicio de la semana para mostrarla
            first_day = datetime(self.year, self.month, 1)
            first_day_of_week = first_day + timedelta(days=-first_day.weekday(), weeks=i)

            week_data = {
                "week_index": i,
                "week_date": first_day_of_week.strftime('%d de %B'),
                "assignments": []
            }
            for key, title in assignment_order:
                if key in weekly_schedule and weekly_schedule[key]:
                    slots = weekly_schedule[key]
                    week_data["assignments"].append({"key": key, "title": title, "slots": slots})
            output["weeks"].append(week_data)

        return output