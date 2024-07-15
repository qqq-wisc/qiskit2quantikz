from fractions import Fraction
import math
import qiskit
import qiskit.circuit
import qiskit.converters
from qiskit.dagcircuit.dagnode import DAGOpNode


def is_rational_multiple_of_pi(value, tolerance=1e-10):
    if not isinstance(value, float):
         return False, None
    ratio = value / math.pi
    fraction = Fraction(ratio).limit_denominator(256)
    return abs(fraction * math.pi - value) < tolerance, fraction

def format_angle(angle):
    result, frac = is_rational_multiple_of_pi(angle)
    if result:
        numerator = frac.numerator if frac.numerator != 1 else ""
        denominator = f"/{frac.denominator}" if frac.denominator != 1 else ""
        pretty_angle = f"{numerator}\pi{denominator}"
    else:
        pretty_angle = angle
    return pretty_angle

def build_array(circ : qiskit.QuantumCircuit):
        array = [[] for _ in range(circ.num_qubits)]
        dag = qiskit.converters.circuit_to_dag(circ)
        layers = dag.multigraph_layers()
        for layer in layers:
            op_nodes = [node for node in layer if isinstance(node, DAGOpNode)]
            support_list = [
                circ.find_bit(qarg)[0]
                for op_node in op_nodes
                for qarg in op_node.qargs
                if op_node.name not in {"barrier", "snapshot", "save", "load", "noise"}
            ]
            unused_qubits = set(range(circ.num_qubits)).difference(support_list)
            for q in unused_qubits:
                    array[q].append('')
            for node in op_nodes:
                if node.name == "barrier":
                    array = [arr[:-1] for arr in array]
                elif len(node.qargs) == 1:
                    q = circ.find_bit(node.qargs[0])[0]
                    name, params = node.op.name, node.op.params
                    array[q].append(f"\gate{{{render_gate_name(name, params)}}}")
                elif node.name == 'cx':
                    ctrl = circ.find_bit(node.qargs[0])[0]
                    tar = circ.find_bit(node.qargs[1])[0]
                    array[ctrl].append(f"\ctrl{{{tar-ctrl}}}")
                    array[tar].append(f"\\targ{{}}")
                elif node.op.label == 'custom_block':
                     qubit_count = len(node.qargs)
                     first = circ.find_bit(node.qargs[0])[0] 
                     array[first].append(f'\gate[{qubit_count}]{{{node.name}}}')
                     for rest in range(first+1, first+qubit_count):
                          array[rest].append("")
                     
                else:
                    raise NotImplementedError
        return array

def render_gate_name(name, params=None):
    if name == 'rz':
        return render_rz(params)
    elif name == 'rx':
        return render_rx(params)
    elif name == 'ry':
        return render_ry(params)
    elif name == 'tdg':
        return "T^{\dag}"
    elif name == 'sdg':
        return "S^{\dag}"
    else:
        param_str =  f"({','.join(params)})" if len(params) > 0 else ""
        return f"{name.upper()}" + param_str

def render_rx(params):
    angle = params[0]
    pretty_angle = format_angle(angle)
    return f"R_x^{{{pretty_angle}}}"

def render_ry(params):
    angle = params[0]
    pretty_angle = format_angle(angle)
    return f"R_z^{{{pretty_angle}}}"

def render_rz(params):
    angle = params[0]
    pretty_angle = format_angle(angle)
    return f"R_z^{{{pretty_angle}}}"

class CircuitDrawing:

    default_quantikz_args = {}

    def __init__(self, circ_spec : int | qiskit.QuantumCircuit, quantikz_args : dict[str,str] = {}):
        if isinstance(circ_spec, qiskit.QuantumCircuit):
            self._circuit = circ_spec
        elif isinstance(circ_spec, int):
             self._circuit = qiskit.QuantumCircuit(circ_spec)
        else:
             raise ValueError("quantum circuit object or qubit count required")
        self._boxes = []
        self._circuit_params = {}
        self._quantikz_args = self.default_quantikz_args.copy()
        self._quantikz_args.update(quantikz_args)
        self.build_array()
    
    def build_array(self):
        self._array = build_array(self._circuit)
    ## Boxes
    def begin_box(self,qubits):
        self._circuit.barrier(qubits)
        self ._boxes.append([min(qubits), qubits,self._circuit.depth()+1, -1])
    
    def end_box(self):
        self ._boxes[-1][3] = self._circuit.depth()+1 - (self._boxes[-1][2])
        qubits = self._boxes[-1][1]
        self._circuit.barrier(qubits)

    def add_boxed_subcirc(self, circ, qubits):
        depth =  circ.depth()
        min_qubit = min(qubits)
        self._boxes.append([min_qubit, qubits, self._circuit.depth()+1, depth])
        self._circuit.barrier()
        self._circuit = self._circuit.compose(circ,qubits=qubits)
        self._circuit.barrier()

    
    def add_gate_groups(self):
        for (start_q, qubits, start_layer, depth) in self._boxes:
            if depth == -1:
                 print(f"Warning: ignoring unclosed box opened at layer {start_layer} on qubits {qubits}")
            else:
                self._array[start_q][start_layer] +=  f"\gategroup[{len(qubits)},steps={depth},style={{rounded corners, dashed, inner sep=0pt, fill=blue!20}}, background]{{}}"

     ## Gates
    def rz(self, angle, qubit):
            if isinstance(angle, float):
                self._circuit.rz(angle, qubit)
            else:
                if angle not in self._circuit_params:
                    self._circuit_params[angle] = qiskit.circuit.Parameter(angle)
                self._circuit.rz(self._circuit_params[angle], qubit)
    
    def rx(self, angle, qubit):
            if isinstance(angle, float):
                self._circuit.rx(angle, qubit)
            else:
                if angle not in self._circuit_params:
                    self._circuit_params[angle] = qiskit.circuit.Parameter(angle)
                self._circuit.rx(self._circuit_params[angle], qubit)
                
    
    def x(self,  qubit):
            self._circuit.x(qubit)

    def y(self,  qubit):
            self._circuit.y(qubit)

    def z(self,  qubit):
            self._circuit.y(qubit)
    
    def h(self,  qubit):
            self._circuit.h(qubit)

    def t(self,  qubit):
            self._circuit.t(qubit)

    def s(self,  qubit):
            self._circuit.s(qubit)
    def tdg(self,  qubit):
        self._circuit.tdg(qubit)

    def sdg(self,  qubit):
            self._circuit.sdg(qubit)

    def cx(self, ctrl, tar):
        self._circuit.cx(ctrl, tar)
    
    def block(self, name, start_qubit, end_qubit,):
        qubit_count = (end_qubit-start_qubit)+1
        temp = qiskit.QuantumCircuit(qubit_count, name=name)
        theta, phi, lam = qiskit.circuit.Parameter("theta"), qiskit.circuit.Parameter("phi"), qiskit.circuit.Parameter("lam")
        for qubit in range(qubit_count):
            temp.u(theta, phi, lam, qubit)
        g = temp.to_instruction(label="custom_block")
        self._circuit.append(g, qargs=range(start_qubit, end_qubit+1))


    # Must refresh the drawing representation before doing any sort of output
    def refresh(self):
        self.build_array()
        self.add_gate_groups()

    def lines(self, standalone=False):
        lines = []
        quantikz_args_str =  " , ".join([f"{k} = {v}" for k,v in self._quantikz_args.items()])
        if standalone:
             lines += ['\\documentclass[border=2px]{standalone}', '\\usepackage{tikz}', '\\usetikzlibrary{quantikz2}', '\\begin{document}']
        lines.append(f"\\begin{{quantikz}}[{quantikz_args_str}]")
        array = self._array
        col_widths = {}
        for col_index in range(len(array[0])):
            col_lens = [len(row[col_index]) for row in array]
            col_widths[col_index] = max(col_lens)+1
        for row_index,row in enumerate(self._array):
            for cell_index,cell in enumerate(row):
             if  0 <  cell_index < len(row)-1:
                pad_len = col_widths[cell_index] - len(cell) 
                padding = " " * pad_len
                self._array[row_index][cell_index] = self._array[row_index][cell_index] + padding
        for i, row in enumerate(self._array):
            line = "&".join(row)
            if i < len(self._array)-1:
                line += "\\\\"
            lines.append(line)
        lines.append(f"\end{{quantikz}}")
        if standalone:
             lines.append("\\end{document}")
        return lines

    def add_qubit_labels(self,labels):
        if labels == "q_n":
            for i,row in enumerate(self._array):
                row[0] = f"\lstick{{$q_{i}$}}"
        elif isinstance(labels, list):
            for i,row in enumerate(self._array):
               row[0] = f"\lstick{{{labels[i]}}}"

    

    def draw(self, qubit_labels=None, standalone=False, filename=None):
        self.refresh()
        if qubit_labels:
             self.add_qubit_labels(qubit_labels)
        lines =  self.lines(standalone=standalone)
        out_str = "\n".join(lines)
        if filename:
            with open(filename, 'w') as f:
                f.write(out_str)
        return out_str


def rewrite_rule(left : CircuitDrawing, right : CircuitDrawing, qubit_labels=None, standalone=False, filename : str = None):
    left._quantikz_args['align equals at'] = left._circuit.num_qubits / 2 + 0.5
    right._quantikz_args['align equals at'] = right._circuit.num_qubits / 2 + 0.5
    left.refresh()
    left.add_qubit_labels(qubit_labels)
    right.refresh()
    right.add_qubit_labels(qubit_labels)
    left_lines = left.lines()
    right_lines = right.lines()
    l_indented = ["    " + left_lines[0]]+["      " + line for line in left_lines[1:-1]] +   ["    " + left_lines[-1]]
    r_indented = ["    " + right_lines[0]]+["      " + line for line in right_lines[1:-1]] + ["    " +right_lines[-1]]
    left = "\n".join(l_indented)
    right = "\n".join(r_indented)
    outstr = ''
    if standalone:
            outstr +='''
\\documentclass[border=2px]{standalone}
\\usepackage{tikz}
\\usetikzlibrary{quantikz2}
\\begin{document}'''
    outstr += f'''
\\begin{{tikzpicture}}
  \\node{{
{left}
        $\\to$
{right}
  }};
\end{{tikzpicture}}'''
    if standalone:
            outstr += "\n\\end{document}"
    if filename:
        with open(filename, 'w') as f:
            f.write(outstr)
    return outstr

def qiskit_rewrite(circ : qiskit.QuantumCircuit | CircuitDrawing, optimization_level=3, basis_gates=None, standalone=False, filename=None):
    if isinstance(circ, CircuitDrawing):
         circ = circ._circuit
    compiled = qiskit.transpile(circ, optimization_level=optimization_level)
    return rewrite_rule(left=CircuitDrawing(circ), right=CircuitDrawing(compiled), standalone=standalone, filename=filename)