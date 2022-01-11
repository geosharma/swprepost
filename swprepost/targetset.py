# This file is part of swprepost, a Python package for surface wave
# inversion pre- and post-processing.
# Copyright (C) 2019-2021 Joseph P. Vantassel (jvantassel@utexas.edu)
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https: //www.gnu.org/licenses/>.

"""Definition of TargetSet class."""

from typing import List
import tarfile as tar
import os

from .modaltarget import ModalTarget
from .check_utils import check_geopsy_version
from .regex import modalcurve_exec
from .meta import __version__

class TargetSet():
    """Container for handling multiple inversion targets."""

    def __init__(self, targets: List[ModalTarget]) -> None:
        """Initialize a `TargetSet` object.

        Parameters
        ----------
        targets : list
            List of `ModalTargets` that define `TargetSet`.

        """
        self.targets = list(targets)

    def cut(self, pmin, pmax, domain="frequency"):
        """Remove data outside of the specified range.

        Parameters
        ----------
        pmin, pmax : float
            New minimum and maximum parameter value in the specified
            domain, respectively.
        domain : {'frequency', 'wavelength'}, optional
            Domain along which to perform the cut.

        Returns
        -------
        None
            May update attributes `frequency`, `velocity`, and
            `velstd`.

        """
        for target in self.targets:
            if isinstance(target, ModalTarget):
                target.cut(pmin=pmin, pmax=pmax, domain=domain)

    def _resample(self, xx, domain="wavelength", inplace=False):
        """Hidden resample function for custom resampling.

        Parameters
        ----------
        xx : ndarray, optional
            Array of new values in the chosen domain.
        domain : {'frequency','wavelength'}, optional
            Resampling domain, default is wavelength.
        inplace : bool, optional
            Determine whether resample is done in place or if the values
            are returned, default is False meaning resampled values are
            returned.

        Returns
        -------
        None or Tuple
            `None` if `resample=False` otherwise returns a `tuple` of
            the form `(frequency, velocity, velstd)`.

        """
        if inplace:
            for target in self.targets:
                if isinstance(target, ModalTarget):
                    target._resample(xx=xx, domain=domain, inplace=inplace)
        else:
            targets = []
            for target in self.targets:
                if isinstance(target, ModalTarget):
                    target = target._resample(xx=xx, domain=domain, inplace=inplace)
                targets.append(target)
            return TargetSet(targets)

    def easy_resample(self, pmin, pmax, pn, res_type="log", domain="wavelength", inplace=False):
        """Resample dispersion curve.

        Resample dispersion curve over a specific range, using log or
        linear sampling in the frequency or wavelength domain.

        Parameters
        ----------
        pmin, pmax : float
            Minimum and maximum parameter value in the resampled
            dispersion data.
        pn : int
            Number of points in the resampled dispersion data.
        res_type : {'log', 'linear'}, optional
            Resample using either logarithmic or linear sampling,
            default is logarithmic.
        domain : {'frequency', 'wavelength'}, optional
            Domain along which to perform the resampling.
        inplace : bool
            Indicating whether the resampling should be done in
            place or if a new `Target` object should be returned.

        Returns
        -------
        None or Target
            If `inplace=True` returns `None`, and may update attributes
            `frequency`, `velocity`, and `velstd`. If `inplace=False`
            a new `Target` object is returned.

        Raises
        ------
        NotImplementedError
            If `res_type` and/or `domain` are not among the options
            specified.

        """
        if inplace:
            for target in self.targets:
                if isinstance(target, ModalTarget):
                    target.easy_resample(pmin, pmax, pn, res_type=res_type, domain=domain, inplace=inplace)
        else:
            targets = []
            for target in self.targets:
                if isinstance(target, ModalTarget):
                    target = target.easy_resample(pmin, pmax, pn, res_type=res_type, domain=domain, inplace=inplace)
                targets.append(target)
            return TargetSet(targets)

    def to_target(self, fname_prefix, version="3.4.2"):
        """Write info to the .target file format used by `Dinver`.

        Parameters
        ----------
        fname_prefix : str
            Name of target file without the .target suffix, a
            relative or full path may be provided.
        version : {'3.4.2', '2.10.1'}, optional
            Version of Geopsy, default is version '3.4.2'.

        Returns
        -------
        None
            Writes file to disk.

        Notes
        -----
        In previous versions of `swprepost` (v1.0.0 and earlier) an
        attempt was made to support all versions of Dinver's .target
        and .param formats. However, this has become untenable due to
        the number and frequency of breaking changes that occur to these
        formats. Therefore, in lieu of supporting all versions,
        `swprepost` will seek to support only those versions directly
        associated with the open-source high-performance computing
        application `swbatch`.

        """
        version = check_geopsy_version(version)

        # TODO (jpv): Handle ell properly.
        __ell_weight = 1
        __ell_def = False
        __ell_mean = 0
        __ell_std = 0

        if version == "2.10.1":

            contents = [
                        "<Dinver>",
                        "  <pluginTag>DispersionCurve</pluginTag>",
                        "  <pluginTitle>Surface Wave Inversion</pluginTitle>"
                        ]

            contents += [
                        "  <TargetList>",
                        "    <ModalCurveTarget type=\"dispersion\">",
                        "      <selected>true</selected>",
                       f"      <misfitWeight>{self.targets[0].dc_weight}</misfitWeight>",
                        "      <minimumMisfit>0</minimumMisfit>",
                        "      <misfitType>L2_Normalized</misfitType>",
                        ]
            
            # TODO (jpv): Fix dc_weight should be an attribute of all ModalTarget and not set individually for each mode.
            # Essentially it needs to be moved to the TargetSet class and out of the ModalTarget class. Take first one for now.

            for target in self.targets:
                target._sort_data()

                contents += [
                        "      <ModalCurve>",
                        "        <name>swprepost</name>",
                       f"        <log>swprepost v{__version__} by Joseph P. Vantassel</log>"
                        ]

                for (polarization, modenumber) in target.description:
                    polarization = polarization.capitalize()
                    contents += [
                        "        <Mode>",
                        "          <slowness>Phase</slowness>",
                       f"          <polarisation>{polarization}</polarisation>",
                        "          <ringIndex>0</ringIndex>",
                       f"          <index>{modenumber}</index>",
                        "        </Mode>"
                        ]

                for x, mean, stddev in zip(target.frequency, target.slowness, target.slostd):
                    contents += [
                        "        <StatPoint>",
                       f"          <x>{x}</x>",
                       f"          <mean>{mean}</mean>",
                       f"          <stddev>{stddev}</stddev>",
                        "          <weight>1</weight>",
                        "          <valid>true</valid>",
                        "        </StatPoint>",
                        ]

                contents += [
                        "      </ModalCurve>",
                        ]

            contents += [
                        "    </ModalCurveTarget>",
                        ]

            contents += [
                        "    <AutocorrTarget>",
                        "      <selected>false</selected>",
                        "      <misfitWeight>1</misfitWeight>",
                        "      <minimumMisfit>0</minimumMisfit>",
                        "      <misfitType>L2_NormalizedBySigmaOnly</misfitType>",
                        "      <AutocorrCurves>",
                        "      </AutocorrCurves>",
                        "    </AutocorrTarget>"
                        ]

            contents += [
                        "    <ModalCurveTarget type=\"ellipticity\">",
                        "      <selected>false</selected>",
                        "      <misfitWeight>1</misfitWeight>",
                        "      <minimumMisfit>0</minimumMisfit>",
                        "      <misfitType>L2_Normalized</misfitType>",
                        "    </ModalCurveTarget>"
                        ]

            # TODO (jpv): Properly handle ell target.
            selected = "true" if __ell_def else "false"
            contents += [
                        "    <ValueTarget type=\"ellipticity peak\">",
                       f"      <selected>{selected}</selected>",
                       f"      <misfitWeight>{__ell_weight}</misfitWeight>",
                        "      <minimumMisfit>0</minimumMisfit>",
                        "      <misfitType>L2_LogNormalized</misfitType>"
                        ]

            contents += [
                        "      <StatValue>",
                       f"        <mean>{__ell_mean}</mean>",
                       f"        <stddev>{__ell_std}</stddev>",
                        "        <weight>1</weight>",
                       f"        <valid>{selected}</valid>",
                        "      </StatValue>",
                        "    </ValueTarget>"
                        ]
            
            contents += [
                        "    <RefractionTarget type=\"Vp\">",
                        "      <selected>false</selected>",
                        "      <misfitWeight>1</misfitWeight>",
                        "      <minimumMisfit>0</minimumMisfit>",
                        "      <misfitType>L2_Normalized</misfitType>",
                        "    </RefractionTarget>"
                        ]

            contents += [
                        "    <RefractionTarget type=\"Vs\">",
                        "      <selected>false</selected>",
                        "      <misfitWeight>1</misfitWeight>",
                        "      <minimumMisfit>0</minimumMisfit>",
                        "      <misfitType>L2_Normalized</misfitType>",
                        "    </RefractionTarget>"
                        ]

            contents += [
                        "  </TargetList>",
                        "</Dinver>",
                        ]

        elif version == "3.4.2":

            contents = [
                        "<Dinver>",
                        "  <pluginTag>DispersionCurve</pluginTag>",
                        "  <pluginTitle>Surface Wave Inversion</pluginTitle>",
                        ]

            contents += [
                        "  <TargetList>",
                        "    <position>0 0 0</position>",
                        "    <DispersionTarget type=\"dispersion\">",
                        "      <selected>true</selected>",
                       f"      <misfitWeight>{self.targets[0].dc_weight}</misfitWeight>",
                        "      <minimumMisfit>0</minimumMisfit>",
                        "      <misfitType>L2_LogNormalized</misfitType>",
                        ]

            # TODO (jpv): Fix dc_weight should be an attribute of all ModalTarget and not set individually for each mode.
            # Essentially it needs to be moved to the TargetSet class and out of the ModalTarget class. Take first one for now.

            for target in self.targets:
                target._sort_data()

                contents += [
                        "      <ModalCurve>",
                        "        <name>swprepost</name>",
                       f"        <log>swprepost v{__version__} by Joseph P. Vantassel</log>",
                        "        <enabled>true</enabled>",
                        ]

                for (polarization, modenumber) in target.description:
                    polarization = polarization.capitalize()
                    contents += [
                        "        <Mode>",
                        "          <value>Signed</value>",
                        "          <slowness>Phase</slowness>",
                       f"          <polarization>{polarization}</polarization>",
                        "          <ringIndex>0</ringIndex>",
                       f"          <index>{modenumber}</index>",
                        "        </Mode>"
                        ]

                for x, mean, stddev in zip(target.frequency, target.slowness, target.logstd):
                    contents += [
                        "        <RealStatisticalPoint>",
                       f"          <x>{x}</x>",
                       f"          <mean>{mean}</mean>",
                       f"          <stddev>{stddev}</stddev>",
                        "          <weight>1</weight>",
                        "          <valid>true</valid>",
                        "        </RealStatisticalPoint>",
                        ]
                contents += [
                        "      </ModalCurve>"
                        ]
            contents += [
                        "    </DispersionTarget>"
                        ]

            contents += [
                        "    <AutocorrTarget>",
                        "      <selected>false</selected>",
                        "      <misfitWeight>1</misfitWeight>",
                        "      <minimumMisfit>0</minimumMisfit>",
                        "      <misfitType>L2_NormalizedBySigmaOnly</misfitType>",
                        "      <AutocorrCurves>",
                        "      </AutocorrCurves>",
                        "    </AutocorrTarget>"
                        ]

            contents += [
                         "    <ModalCurveTarget type=\"ellipticity\">",
                         "      <selected>false</selected>",
                         "      <misfitWeight>1</misfitWeight>",
                         "      <minimumMisfit>0</minimumMisfit>",
                         "      <misfitType>L2_Normalized</misfitType>",
                         "    </ModalCurveTarget>"
                         ]

            # TODO (jpv): Properly handle ell target.
            selected = "true" if __ell_def else "false"
            contents += [
                        "    <EllipticityPeakTarget type=\"ellipticity peak\">",
                        "      <minimumAmplitude>0</minimumAmplitude>",
                        "      <RealStatisticalValue>",
                        "        <mean>0</mean>",
                        "        <stddev>0</stddev>",
                       f"        <weight>{__ell_weight}</weight>",
                       f"        <valid>{selected}</valid>",
                        "      </RealStatisticalValue>",
                        "    </EllipticityPeakTarget>",
                        ]

            contents += [
                        "    <RefractionTarget type=\"Vp\">",
                        "      <selected>false</selected>",
                        "      <misfitWeight>1</misfitWeight>",
                        "      <minimumMisfit>0</minimumMisfit>",
                        "      <misfitType>L2_Normalized</misfitType>",
                        "    </RefractionTarget>"
                        ]

            contents += [
                        "    <RefractionTarget type=\"Vs\">",
                        "      <selected>false</selected>",
                        "      <misfitWeight>1</misfitWeight>",
                        "      <minimumMisfit>0</minimumMisfit>",
                        "      <misfitType>L2_Normalized</misfitType>",
                        "    </RefractionTarget>"
                        ]

            contents += [
                        "    <MagnetoTelluricTarget>",
                        "      <selected>false</selected>",
                        "      <misfitWeight>1</misfitWeight>",
                        "      <minimumMisfit>0</minimumMisfit>",
                        "      <misfitType>L2_Normalized</misfitType>",
                        "    </MagnetoTelluricTarget>"
                        ]

            contents += [
                        "  </TargetList>",
                        "</Dinver>"
                        ]

        with open("contents.xml", "w", encoding="utf-8") as f:
            for row in contents:
                f.write(row+"\n")
        with tar.open(fname_prefix+".target", "w:gz") as f:
            f.add("contents.xml")
        os.remove("contents.xml")

    @classmethod
    def from_target(cls, fname_prefix, version="3.4.2"):
        """Create from `TargetSet` from .target file.

        Note this method is still largely experimental and may
        not work for all cases.

        Parameters
        ----------
        fname_prefix : str
            Name of target file to be opened excluding the `.target`
            suffix, may include the relative or full path.
        version : {'3.4.2', '2.10.1'}, optional
            Version of Geopsy, default is version '3.4.2'.

        Returns
        -------
        TargetSet
            Instantiated `TargetSet` object.

        Raises
        ------
        NotImplementedError
            If `version` does not match the options provided.

        Notes
        -----
        In previous versions of `swprepost` (v1.0.0 and earlier) an
        attempt was made to support all versions of Dinver's .target
        and .param formats. However, this has become untenable due to
        the number and frequency of breaking changes that occur to these
        formats. Therefore, in lieu of supporting all versions,
        `swprepost` will seek to support only those versions directly
        associated with the open-source high-performance computing
        application `swbatch`.

        """
        with tar.open(fname_prefix+".target", "r:gz") as a:
            a.extractall()

        # TODO (jpv): Make thread safe, race condition on os.remove.
        try:
            with open("contents.xml", "r", encoding="utf-8") as f:
                text = f.read()
            if "<Dinver>" != text[:len("<Dinver>")]:
                raise RuntimeError
        except (UnicodeDecodeError, RuntimeError):
            with open("contents.xml", "r", encoding="utf_16_le") as f:
                text = f.read()
            # start from index 1 to skip the byte order mark (BOM).
            # the BOM for this format is \ufeff
            # see https://en.wikipedia.org/wiki/Byte_order_mark.
            if "<Dinver>" != text[1:len(r" <Dinver>")]:
                raise ValueError("File encoding not recognized.")
        finally:
            os.remove("contents.xml")

        mc_texts = modalcurve_exec.findall(text)
        targets = []
        for mc_text in mc_texts:
            args = ModalTarget._parse_modeltarget_from_text(mc_text, version=version)
            targets.append(ModalTarget(*args))

        return cls(targets)

    def __eq__(self, obj):
        """Check if two `TargetSet` objects are equal."""
        if not isinstance(obj, TargetSet):
            return False

        if len(self.targets) != len(obj.targets):
            return False

        for a, b in zip(self.targets, obj.targets):
            if a != b:
                return False
        return True

    def __repr__(self):
        """Unambiguous representation of a `TargetSet`."""
        repr=""
        for target in self.targets:
            repr += f"{target.__repr__()}\n"
        return repr

    def __str__(self):
        """Human readable representation of a `TargetSet`."""
        return f"TargetSet with {len(self.targets)} targets."
