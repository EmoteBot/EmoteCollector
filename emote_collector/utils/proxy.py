# Emote Collector collects emotes from other servers for use by people without Nitro
# Copyright © 2018–2019 lambda#0987
#
# Emote Collector is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Emote Collector is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Emote Collector. If not, see <https://www.gnu.org/licenses/>.

class ObjectProxy:
	def __init__(self, thunk):
		vars(self)[f'_{type(self).__name__}__thunk'] = thunk

	for meth_name in (f'__{meth_name}__' for meth_name in (
		'call await enter exit aenter aexit len bool lt le eq ne gt ge dir delattr getitem setitem '
		'delitem setattr length_hint missing iter reversed contains add sub mul matmul truediv floordiv mod divmod pow '
		'lshift rshift and xor or radd rsub rmul rmatmul rtruediv rfloordiv rmod rdivmod rpow rlshift rrshift rand '
		'rxor ror iadd isub imul imatmul itruediv ifloordiv imod ipow ilshift irshift iand ixor ior neg abs pos abs '
		'invert complex int float index round trunc floor ceil aiter anext'
	).split()):
		# avoid having to pass in meth_name as a default argument so we can avoid name conflicts
		def closure(meth_name=meth_name):
			def meth(self, *args, **kwargs):
				return getattr(self.__thunk(), meth_name)(*args, **kwargs)
			return meth
		meth = closure()
		meth.__name__ = meth_name
		vars()[meth_name] = meth

	del closure, meth, meth_name

	def __getattr__(self, k):
		return getattr(self.__thunk(), k)

	def __repr__(self):
		return f'<ObjectProxy for {self.__thunk!r}()>'
